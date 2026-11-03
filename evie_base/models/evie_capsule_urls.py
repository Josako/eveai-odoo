"""Server side of the reusable Evie capsule URLs component.

Lists the URL capsules linked to a record's capsule in Evie (the
``CRM_ENTITY_HAS_URL`` relation) so the client widget can render them as
external links (odoo-lead-linked-urls). Any record exposing a capsule id
field can use it. Records the user may write additionally offer linking a
URL and unlinking URLs, like the linked documents.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.evie_base.tools import (
    evie_check_record_write, evie_record_can_write, evie_record_capsule_id)

_logger = logging.getLogger(__name__)


class EvieCapsuleUrls(models.AbstractModel):
    _name = 'evie.capsule.urls'
    _description = 'Evie Capsule URLs'

    @api.model
    def get_urls(self, res_model, res_id, capsule_id_field=None):
        """URL capsules linked to the record's capsule, newest first.

        Never raises on Evie failures.

        Returns:
            dict: ``{'ok': bool, 'urls': [...], 'linked': bool,
            'can_write': bool}``
        """
        can_write = evie_record_can_write(self.env, res_model, res_id)
        capsule_id = evie_record_capsule_id(self.env, res_model, res_id, capsule_id_field)
        if not capsule_id:
            return {'ok': True, 'urls': [], 'linked': False, 'can_write': can_write}
        ok, data = self.env['evie.webhook'].get_for_json(
            '/capsule-urls', params={'capsule_id': capsule_id})
        if not ok:
            _logger.warning("Evie URL listing failed for capsule %s: %s", capsule_id, data)
            return {'ok': False, 'urls': [], 'linked': True, 'can_write': can_write}
        return {'ok': True, 'urls': data.get('urls', []), 'linked': True,
                'can_write': can_write}

    @api.model
    def link_url(self, res_model, res_id, url, label=None, kind=None, capsule_id_field=None):
        """Link an external URL to the record's capsule.

        Idempotent (Evie dedupes per capsule–URL pair). Raises on Evie
        failures so the widget can notify.
        """
        evie_check_record_write(self.env, res_model, res_id)
        capsule_id = evie_record_capsule_id(self.env, res_model, res_id, capsule_id_field)
        if not capsule_id:
            raise UserError(_("This record is not linked to Evie yet."))
        payload = {'capsule_id': capsule_id, 'url': (url or '').strip()}
        if label:
            payload['label'] = label
        if kind:
            payload['kind'] = kind
        ok, data = self.env['evie.webhook'].post_for_json('/capsule-url-link', payload)
        if not ok:
            _logger.warning("Evie URL link failed for capsule %s: %s", capsule_id, data)
            raise UserError(_("Could not link the URL (%s).") % data)
        return data

    @api.model
    def unlink_url(self, res_model, res_id, relation_id, capsule_id_field=None):
        """Remove one of the record's URL links (soft delete in Evie).

        Raises on Evie failures so the widget can keep the list unchanged.
        """
        evie_check_record_write(self.env, res_model, res_id)
        result = self.get_urls(res_model, res_id, capsule_id_field)
        if not result['ok']:
            raise UserError(_("Evie is unreachable; try again in a moment."))
        if not any(entry['relation_id'] == int(relation_id) for entry in result['urls']):
            raise UserError(_("This URL is not linked to the record."))
        ok, data = self.env['evie.webhook'].post_for_json(
            '/capsule-url-unlink', {'relation_id': int(relation_id)})
        if not ok:
            _logger.warning("Evie URL unlink failed for relation %s: %s", relation_id, data)
            raise UserError(_("Could not unlink the URL (%s).") % data)
        return True
