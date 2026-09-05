"""Reusable capsule-link mixin for Evie mirror models (odoo-marketing-adapter).

Mirror models are the second projection pattern: where native Odoo models
carry ``x_evie_*`` anchors (crm.lead, mail.activity), capsules without a
native counterpart project onto *dedicated* Odoo models. This mixin carries
the link state every mirror needs and the shared Odoo → Evie event
plumbing:

- ``capsule_id``      — the stable Evie identity; the ONLY matching key
- ``capsule_version`` — version token of the capsule definition
- ``capsule_url``     — static deeplink to Evie (admin entry carrying the
  capsule reference; the live detail opens via the view-token button)
- ``sync_state``      — synced / pending / conflict / error
- ``last_sync_date``  — last successful Evie ↔ Odoo sync
- ``local_dirty``     — locally edited while Evie was unreachable; the
  write-back is queued and retried by the scheduled job (design D8)

Behaviour contracts shared by all mirror models:

- Mirror records are created by the Evie sync only (v1: edit-only). A
  manual create — anything without the echo-guard context the sync writes
  carry — is refused server-side; views hide the create buttons too.
- Local edits notify Evie via the generic ``/mirror-upsert`` event (a
  hint; Evie reads the record fresh and reconciles value-based). A failed
  notification marks the record ``local_dirty`` instead of scheduling an
  activity: mirrors are sync-owned records, the retry job is the remedy.
- ``evie_retry_local_dirty`` is the cron entry point: re-notify every
  dirty record; a successful notification clears the flag. Inbound
  application on the Evie side is value-idempotent, so replaying queued
  edits is safe.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: Echo-guard context key: sync writes (Evie → Odoo) carry this flag so
#: automations and guards can tell sync writes apart from local edits.
#: Same convention as evie_crm's EVIE_SYNC_CONTEXT.
EVIE_SYNC_CONTEXT_KEY = 'evie_skip_phase_event'


class EvieCapsuleLink(models.AbstractModel):
    _name = 'evie.capsule.link'
    _description = 'Evie Capsule Link (mirror-model mixin)'

    capsule_id = fields.Char(
        string='Evie Capsule ID', readonly=True, index=True, copy=False,
        help='Stable Evie Data Capsule identity — the only matching key.')
    capsule_version = fields.Char(
        string='Capsule Version', readonly=True, copy=False,
        help='Version token of the capsule definition at the last sync.')
    capsule_url = fields.Char(
        string='Evie Link', readonly=True, copy=False,
        help='Static deeplink to Evie (the live detail opens via the '
             'view-token button).')
    sync_state = fields.Selection(
        [('pending', 'Pending'), ('synced', 'Synced'),
         ('conflict', 'Conflict'), ('error', 'Error')],
        string='Sync State', default='pending', readonly=True, copy=False)
    last_sync_date = fields.Datetime(
        string='Last Synced', readonly=True, copy=False)
    local_dirty = fields.Boolean(
        string='Local Changes Pending', default=False, readonly=True,
        copy=False,
        help='Set when a local edit could not be written back to Evie; '
             'the scheduled job retries until Evie is reachable again.')

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        """Mirror records are sync-created only (v1: edit-only in Odoo)."""
        if not self.env.context.get(EVIE_SYNC_CONTEXT_KEY):
            raise UserError(_(
                "%s records are created by the Evie synchronisation. "
                "Create the object in Evie; it appears here automatically."
            ) % self._description)
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Odoo → Evie events (hints; Evie reads the record fresh)
    # ------------------------------------------------------------------

    def evie_notify_upsert(self):
        """Notify Evie of a local edit on a shared (both-direction) field.

        Called by the module's ``[AUTO] Evie`` automation rules. No-op for
        writes carrying the echo-guard context (Evie sync writes). A failed
        notification queues the write-back via ``local_dirty`` (the retry
        job is the remedy — mirrors are sync-owned records, so no activity
        is scheduled like on the lead).
        """
        if self.env.context.get(EVIE_SYNC_CONTEXT_KEY):
            return

        for record in self:
            ok, detail = self.env['evie.webhook'].post('/mirror-upsert', {
                'odoo_model': record._name,
                'remote_id': record.id,
                'capsule_id': record.capsule_id or None,
            })
            if not ok and detail != 'not_configured':
                _logger.warning(
                    "Evie mirror-upsert notify failed for %s #%s (%s) — "
                    "marked local_dirty", record._name, record.id, detail)
                record._evie_set_local_dirty(True)

    @api.model
    def evie_retry_local_dirty(self):
        """Cron entry point: retry the queued write-backs for this model.

        Re-notifies every local_dirty record; a successful notification
        clears the flag. Inbound application on the Evie side is
        value-idempotent, so replaying queued edits is safe.
        """
        dirty = self.sudo().search([('local_dirty', '=', True)])
        if not dirty:
            return
        _logger.info(
            "Evie local_dirty retry: %s record(s) of %s", len(dirty), self._name)
        for record in dirty:
            if not self.env['evie.webhook'].is_configured():
                return  # pointless until the connection is configured
            ok, detail = self.env['evie.webhook'].post('/mirror-upsert', {
                'odoo_model': record._name,
                'remote_id': record.id,
                'capsule_id': record.capsule_id or None,
            })
            if ok:
                record._evie_set_local_dirty(False)
            else:
                _logger.info(
                    "Evie local_dirty retry still failing for %s #%s (%s)",
                    record._name, record.id, detail)

    def _evie_set_local_dirty(self, dirty):
        """Write the flag with the echo-guard context (never re-triggers
        the upsert automations; the watched fields exclude local_dirty)."""
        self.with_context(**{EVIE_SYNC_CONTEXT_KEY: True}) \
            .write({'local_dirty': dirty})

    # ------------------------------------------------------------------
    # Open in Evie (the evie_link widget contract)
    # ------------------------------------------------------------------

    def action_evie_open(self, kind, reference):
        """Single dispatcher behind every 'open in Evie' link on the form.

        Same contract as the crm.lead dispatcher (the ``evie_link`` field
        widget calls ``action_evie_open(kind, reference)`` on the record):
        exchanges the integration API key for a short-lived view token and
        returns the URL to open. Mirror models only link capsules, so
        'capsule' is the only supported kind. ``capsule_url`` is only the
        static fallback — the token flow is the live detail link.
        """
        self.ensure_one()
        if kind != 'capsule':
            raise UserError(_("Unknown Evie reference type '%s'.") % kind)
        if not reference:
            raise UserError(_("No Evie capsule is linked to this record yet."))
        user = self.env.user
        ok, data = self.env['evie.webhook'].post_for_json('/view-token', {
            'kind': 'capsule',
            'capsule_id': int(reference),
            'user': {'name': user.name, 'email': user.email, 'id': user.id},
        })
        if not ok:
            raise UserError(_("Could not open the Evie capsule (%s).") % data)
        return {
            'type': 'ir.actions.act_url',
            'url': data['view_url'],
            'target': 'new',
        }
