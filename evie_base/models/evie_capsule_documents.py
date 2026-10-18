"""Server side of the reusable Evie capsule documents component.

Lists the documents linked to a record's capsule in Evie (the
``CRM_ENTITY_HAS_DOCUMENT`` relation) and opens them in the Evie external
document view. Any record exposing a capsule id field can use it.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.evie_base.tools import evie_open_action, evie_record_capsule_id

_logger = logging.getLogger(__name__)


class EvieCapsuleDocuments(models.AbstractModel):
    _name = 'evie.capsule.documents'
    _description = 'Evie Capsule Documents'

    @api.model
    def get_documents(self, res_model, res_id, capsule_id_field=None):
        """Documents linked to the record's capsule, newest first.

        Never raises on Evie failures.

        Returns:
            dict: ``{'ok': bool, 'documents': [...], 'linked': bool}``
        """
        capsule_id = evie_record_capsule_id(self.env, res_model, res_id, capsule_id_field)
        if not capsule_id:
            return {'ok': True, 'documents': [], 'linked': False}
        ok, data = self.env['evie.webhook'].get_for_json(
            '/capsule-documents', params={'capsule_id': capsule_id})
        if not ok:
            _logger.warning("Evie document listing failed for capsule %s: %s", capsule_id, data)
            return {'ok': False, 'documents': [], 'linked': True}
        return {'ok': True, 'documents': data.get('documents', []), 'linked': True}

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
