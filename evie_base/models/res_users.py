"""res.users extension: Evie-synced user preferences
(odoo-user-preferences-sync).

Makes the two user preferences Evie acts on editable from Odoo's own My
Preferences screen and keeps them in sync bi-directionally:

* the native ``lang`` field doubles as the Evie preferred language —
  translated through the tenant's shared ``evie.language_map`` before
  notifying Evie (an unmapped language is skipped, never cleared);
* ``x_evie_booking_page_url`` mirrors the USER_CUSTOMISATION
  ``booking_page_url`` option — Evie stays the validating authority.

Loop prevention (design D5): writes carrying the ``evie_sync_origin``
context flag (Evie's own outbound writes) never notify Evie back, and a
write whose effective values did not change never fires the webhook.
"""

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)

#: Context flag set by Evie's outbound preference writes so this hook does
#: not echo them back to Evie.
EVIE_SYNC_CONTEXT_KEY = 'evie_sync_origin'

#: res.users fields mirrored to the Evie user preferences.
EVIE_SYNCED_FIELDS = ('lang', 'x_evie_booking_page_url')


class ResUsers(models.Model):
    _inherit = 'res.users'

    x_evie_booking_page_url = fields.Char(
        string='Booking Page URL',
        copy=False,
        help="Public URL of your online booking page (e.g. Calendly). "
             "Synced with Evie, which offers it to visitors who request an "
             "appointment, in preference over the company booking page.",
    )

    @property
    def SELF_READABLE_FIELDS(self):
        """Odoo 19 pattern: extend the property so a user may read their
        own booking page URL without administrator rights."""
        return super().SELF_READABLE_FIELDS + ['x_evie_booking_page_url']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['x_evie_booking_page_url']

    def write(self, vals):
        watched = {key for key in EVIE_SYNCED_FIELDS if key in vals}
        notify = bool(watched) and not self.env.context.get(EVIE_SYNC_CONTEXT_KEY)
        old_values = {}
        if notify:
            for user in self:
                old_values[user.id] = {key: user[key] or False for key in watched}
        result = super().write(vals)
        if notify:
            for user in self:
                changed = {
                    key for key in watched
                    if (user[key] or False) != old_values[user.id][key]
                }
                if changed:
                    user._evie_notify_preferences(changed)
        return result

    def _evie_notify_preferences(self, changed_fields):
        """Push the changed synced preferences to Evie (fire-and-forget).

        Failures never roll back the user's save: they are logged, and the
        next preference change converges Evie again.
        """
        payload = {
            'external_user': {
                'id': self.id,
                'name': self.name,
                'email': self.email or self.login,
            },
        }
        if 'x_evie_booking_page_url' in changed_fields:
            # None clears the option Evie-side.
            payload['customisation_options'] = {
                'booking_page_url': self.x_evie_booking_page_url or None,
            }
        if 'lang' in changed_fields:
            evie_code = self._evie_language_code()
            if evie_code:
                payload['preferred_language'] = evie_code
        if not any(key in payload
                   for key in ('preferred_language', 'customisation_options')):
            return
        ok, detail = self.env['evie.webhook'].post('/user-preferences', payload)
        if not ok and detail != 'not_configured':
            _logger.warning(
                "Evie user-preferences notification failed for user %s: %s",
                self.id, detail)

    def _evie_language_code(self):
        """Translate this user's Odoo language to the Evie ISO 639-1 code
        via the tenant's shared language map.

        Returns None when the language is unmapped — the sync then skips
        the language entirely (it never clears), consistent with the lead
        language sync.
        """
        if not self.lang:
            return None
        lang = self.env['res.lang'].sudo().search(
            [('code', '=', self.lang)], limit=1)
        if not lang:
            return None
        mapping = self.env['evie.language_map'].sudo().search(
            [('odoo_lang_id', '=', lang.id)], limit=1)
        return mapping.evie_language if mapping else None
