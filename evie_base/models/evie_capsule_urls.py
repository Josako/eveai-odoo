"""Server side of the reusable Evie capsule URLs component.

Lists the URL capsules linked to a record's capsule in Evie (the
``CRM_ENTITY_HAS_URL`` relation) so the client widget can render them as
external links (odoo-lead-linked-urls). Any record exposing a capsule id
field can use it. Read-only: linking and unlinking stay Evie-side.
"""

import logging

from odoo import api, models

from odoo.addons.evie_base.tools import evie_record_capsule_id

_logger = logging.getLogger(__name__)


class EvieCapsuleUrls(models.AbstractModel):
    _name = 'evie.capsule.urls'
    _description = 'Evie Capsule URLs'

    @api.model
    def get_urls(self, res_model, res_id, capsule_id_field=None):
        """URL capsules linked to the record's capsule, newest first.

        Never raises on Evie failures.

        Returns:
            dict: ``{'ok': bool, 'urls': [...], 'linked': bool}``
        """
        capsule_id = evie_record_capsule_id(self.env, res_model, res_id, capsule_id_field)
        if not capsule_id:
            return {'ok': True, 'urls': [], 'linked': False}
        ok, data = self.env['evie.webhook'].get_for_json(
            '/capsule-urls', params={'capsule_id': capsule_id})
        if not ok:
            _logger.warning("Evie URL listing failed for capsule %s: %s", capsule_id, data)
            return {'ok': False, 'urls': [], 'linked': True}
        return {'ok': True, 'urls': data.get('urls', []), 'linked': True}
