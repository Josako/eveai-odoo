"""Server side of the personal outreach link copy widget
(dual-personal-link-surfaces).

Fetches a record's short personal links — both pinned variants (website
and chat-direct) — from the Evie copy-surface endpoints on demand. The
personal link code itself is never stored in Odoo — only the composed
short URLs pass through on fetch (the "never synced" rule stays
intact).

The fetch never raises: failures return ``ok: False`` with a message so
the OWL widget degrades gracefully and the form keeps working.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

#: Copy-surface endpoint per record kind, relative to the configured Evie
#: base URL.
_ENDPOINTS = {
    'lead': '/personal-link',
    'activity': '/activity-personal-link',
}


class EviePersonalLink(models.AbstractModel):
    _name = 'evie.personal.link'
    _description = 'Evie Personal Outreach Link'

    @api.model
    def get_personal_link(self, kind, capsule_id):
        """Fetch both short personal link variants for a record from Evie.

        Args:
            kind: 'lead' or 'activity' — selects the endpoint variant.
            capsule_id: the record's Evie capsule id (x_evie_capsule_id).

        Returns:
            dict: ``{'ok': True, 'website': {...}, 'chat': {...}}`` on
            success (each variant a dict with ``url``, ``target_url``,
            ``resolved_target`` and ``clicks``, or None when that variant
            could not be composed), ``{'ok': False, 'message': ...}``
            otherwise. Never raises.
        """
        endpoint = _ENDPOINTS.get(kind)
        if not endpoint or not capsule_id:
            return {'ok': False,
                    'message': 'unsupported kind or missing capsule id'}
        ok, data = self.env['evie.webhook'].get_for_json(
            endpoint, params={'capsule_id': str(capsule_id)})
        if not ok:
            _logger.warning(
                "Evie personal link fetch failed (%s, capsule %s): %s",
                kind, capsule_id, data)
            return {'ok': False, 'message': str(data)}
        website = data.get('website')
        chat = data.get('chat')
        if not website and not chat:
            return {'ok': False,
                    'message': data.get('message') or 'no link resolvable'}
        return {'ok': True, 'website': website, 'chat': chat}
