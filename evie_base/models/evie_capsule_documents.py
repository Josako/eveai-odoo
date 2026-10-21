"""Server side of the reusable Evie capsule documents component.

Lists the documents linked to a record's capsule in Evie (the
``CRM_ENTITY_HAS_DOCUMENT`` relation) and opens them in the Evie external
document view. Any record exposing a capsule id field can use it. Records
the user may write additionally offer linking (via the Evie picker
breakout) and unlinking of documents.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.evie_base.tools import evie_open_action, evie_record_capsule_id

_logger = logging.getLogger(__name__)


class EvieCapsuleDocuments(models.AbstractModel):
    _name = 'evie.capsule.documents'
    _description = 'Evie Capsule Documents'

    def _evie_check_write(self, res_model, res_id):
        """The record when the user may write it, else raise."""
        if res_model not in self.env or not res_id:
            raise UserError(_("Unknown record."))
        record = self.env[res_model].with_context(active_test=False).browse(int(res_id)).exists()
        if not record:
            raise UserError(_("The record no longer exists."))
        record.check_access('write')
        return record

    @api.model
    def get_documents(self, res_model, res_id, capsule_id_field=None):
        """Documents linked to the record's capsule, newest first.

        Never raises on Evie failures.

        Returns:
            dict: ``{'ok': bool, 'documents': [...], 'linked': bool,
            'can_write': bool}``
        """
        can_write = False
        if res_model in self.env and res_id:
            record = self.env[res_model].with_context(
                active_test=False).browse(int(res_id)).exists()
            can_write = bool(record) and record.has_access('write')
        capsule_id = evie_record_capsule_id(self.env, res_model, res_id, capsule_id_field)
        if not capsule_id:
            return {'ok': True, 'documents': [], 'linked': False, 'can_write': can_write}
        ok, data = self.env['evie.webhook'].get_for_json(
            '/capsule-documents', params={'capsule_id': capsule_id})
        if not ok:
            _logger.warning("Evie document listing failed for capsule %s: %s", capsule_id, data)
            return {'ok': False, 'documents': [], 'linked': True, 'can_write': can_write}
        return {'ok': True, 'documents': data.get('documents', []),
                'linked': True, 'can_write': can_write}

    @api.model
    def open_document(self, res_model, res_id, document_version_id, capsule_id_field=None):
        """Open one of the record's capsule documents in Evie (new tab)."""
        result = self.get_documents(res_model, res_id, capsule_id_field)
        if not result['ok']:
            raise UserError(_("Evie is unreachable; try again in a moment."))
        if not any(document['document_version_id'] == int(document_version_id)
                   for document in result['documents']):
            raise UserError(_("This document is not linked to the record."))
        return evie_open_action(self.env, 'document', document_version_id)

    @api.model
    def open_picker(self, res_model, res_id, capsule_id_field=None):
        """Open the Evie document picker breakout for the record's capsule.

        The picker (a short-lived, user-scoped Evie popup) links an existing
        Evie document to the capsule; the component refreshes on window
        focus, so a freshly linked document appears automatically.
        """
        self._evie_check_write(res_model, res_id)
        capsule_id = evie_record_capsule_id(self.env, res_model, res_id, capsule_id_field)
        if not capsule_id:
            raise UserError(_("This record is not linked to Evie yet."))
        return evie_open_action(self.env, 'document_picker', capsule_id)

    @api.model
    def link_document(self, res_model, res_id, document_id, document_type=None,
                      document_description=None, shared_in_outreach=None,
                      capsule_id_field=None):
        """Link an existing Evie document to the record's capsule.

        Idempotent (Evie dedupes per capsule–document pair). Returns the
        link result; raises on Evie failures so the widget can notify.
        """
        self._evie_check_write(res_model, res_id)
        capsule_id = evie_record_capsule_id(self.env, res_model, res_id, capsule_id_field)
        if not capsule_id:
            raise UserError(_("This record is not linked to Evie yet."))
        payload = {'capsule_id': capsule_id, 'document_id': int(document_id)}
        if document_type:
            payload['document_type'] = document_type
        if document_description:
            payload['document_description'] = document_description
        if shared_in_outreach is not None:
            payload['shared_in_outreach'] = bool(shared_in_outreach)
        ok, data = self.env['evie.webhook'].post_for_json(
            '/capsule-document-link', payload)
        if not ok:
            _logger.warning("Evie document link failed for capsule %s: %s",
                            capsule_id, data)
            raise UserError(_("Could not link the document (%s).") % data)
        return data

    @api.model
    def unlink_document(self, res_model, res_id, relation_id, capsule_id_field=None):
        """Remove one of the record's document links (soft delete in Evie).

        The document itself is never deleted. Raises on Evie failures so
        the widget can keep the list unchanged.
        """
        self._evie_check_write(res_model, res_id)
        result = self.get_documents(res_model, res_id, capsule_id_field)
        if not result['ok']:
            raise UserError(_("Evie is unreachable; try again in a moment."))
        if not any(document['relation_id'] == int(relation_id)
                   for document in result['documents']):
            raise UserError(_("This document is not linked to the record."))
        ok, data = self.env['evie.webhook'].post_for_json(
            '/capsule-document-unlink', {'relation_id': int(relation_id)})
        if not ok:
            _logger.warning("Evie document unlink failed for relation %s: %s",
                            relation_id, data)
            raise UserError(_("Could not unlink the document (%s).") % data)
        return True

    @api.model
    def set_shared_in_outreach(self, res_model, res_id, relation_id, shared,
                               capsule_id_field=None):
        """Toggle the shared-in-outreach flag on one of the record's
        document relations (tracked-document-links): shared documents of an
        activity go out as tracked short links in composed outreach.

        Returns the new flag value; raises on Evie failures so the widget
        can revert the checkbox.
        """
        result = self.get_documents(res_model, res_id, capsule_id_field)
        if not result['ok']:
            raise UserError(_("Evie is unreachable; try again in a moment."))
        if not any(document['relation_id'] == int(relation_id)
                   for document in result['documents']):
            raise UserError(_("This document is not linked to the record."))
        ok, data = self.env['evie.webhook'].post_for_json(
            '/capsule-document-share',
            {'relation_id': int(relation_id), 'shared_in_outreach': bool(shared)})
        if not ok:
            _logger.warning("Evie shared-in-outreach toggle failed for relation %s: %s",
                            relation_id, data)
            raise UserError(_("Evie is unreachable; try again in a moment."))
        return bool(data.get('shared_in_outreach'))
