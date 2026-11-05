"""Server-side personal outreach destination and copy-widget calls.

Fetches dynamic named destinations and preference choices from Evie on
demand. Personal link codes are never stored in Odoo; only short aliases,
long target URLs and destination metadata pass through these methods.
Failures return ``ok: False`` so forms keep working.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

_ENDPOINTS = {
    'lead': '/personal-link',
    'activity': '/activity-personal-link',
}


class EviePersonalLink(models.AbstractModel):
    _name = 'evie.personal.link'
    _description = 'Evie Personal Outreach Link'

    @api.model
    def get_personal_link(self, kind, capsule_id):
        """Return the dynamic destination collection for a record."""
        endpoint = _ENDPOINTS.get(kind)
        if not endpoint or not capsule_id:
            return {'ok': False,
                    'message': 'unsupported kind or missing capsule id'}
        ok, data = self.env['evie.webhook'].get_for_json(
            endpoint, params={'capsule_id': str(capsule_id)})
        if not ok:
            _logger.warning(
                'Evie personal link fetch failed (%s, capsule %s): %s',
                kind, capsule_id, data)
            return {'ok': False, 'message': str(data)}
        destinations = data.get('destinations') or []
        if not destinations:
            return {'ok': False,
                    'message': data.get('message') or 'no link resolvable'}
        return {'ok': True, 'destinations': destinations}

    @api.model
    def get_destination_options(self, capsule_id=None):
        """Return preference choices without minting tracked aliases."""
        params = ({'capsule_id': str(capsule_id)} if capsule_id else {})
        ok, data = self.env['evie.webhook'].get_for_json(
            '/outreach-destination-options', params=params)
        if not ok:
            _logger.warning('Evie destination options fetch failed: %s', data)
            return {'ok': False, 'message': str(data)}
        return {'ok': True,
                'destinations': data.get('destinations') or []}
