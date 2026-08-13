"""Evie fields and reverse-translation logic on crm.lead.

The ``x_evie_`` fields are the anchor contract with the Evie platform:

* ``x_evie_capsule_id`` — the Evie Data Capsule this record is linked to
  (source-of-truth coupling; survives lead→opportunity conversion)
* ``x_evie_phase`` — the Evie funnel phase, always kept consistent
* ``x_evie_last_synced`` — last push-sync timestamp written by Evie

``evie_apply_stage_to_phase`` is called by the ``[AUTO] Evie: stage → phase``
automation rule when a user changes the stage (e.g. drags a card in the
Kanban). It reverse-maps the stage via ``evie.phase_stage_map``, updates the
anchor and notifies Evie with the already-translated phase — Evie never
performs a stage lookup itself.
"""

import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)

#: Context flag set by Evie's own writes so the automation rule does not
#: echo Evie-originated stage changes back to Evie.
EVIE_SYNC_CONTEXT_KEY = 'evie_skip_phase_event'


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    x_evie_capsule_id = fields.Char(
        string='Evie Capsule ID',
        index=True,
        copy=False,
        tracking=True,
        help="ID of the linked Evie Data Capsule (source-of-truth coupling).",
    )
    x_evie_phase = fields.Char(
        string='Evie Phase',
        index=True,
        copy=False,
        tracking=True,
        help="Stable Evie funnel phase. Written by every Evie sync and kept "
             "consistent when the stage changes.",
    )
    x_evie_last_synced = fields.Datetime(
        string='Evie Last Synced',
        copy=False,
        readonly=True,
        help="Timestamp of the last Evie → Odoo sync for this record.",
    )

    def evie_apply_stage_to_phase(self):
        """Reverse-map stage → phase, update the anchor and notify Evie.

        Called by the ``[AUTO] Evie: stage → phase`` automation rule. No-op
        for writes originating from Evie itself (context flag) to prevent
        echo loops.
        """
        if self.env.context.get(EVIE_SYNC_CONTEXT_KEY):
            return

        mapping = self.env['evie.phase_stage_map']
        for lead in self:
            if not lead.stage_id:
                continue

            phase = mapping.phase_for_stage(lead.stage_id.id)
            if not phase:
                # Visible signal, not a silent drop.
                lead.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=lead.user_id.id or self.env.user.id,
                    note=_("Evie: stage '%s' has no entry in the phase mapping "
                           "(Evie ▸ Configuration ▸ Phase Mapping). The Evie "
                           "phase was not updated.") % lead.stage_id.name,
                )
                continue

            if lead.x_evie_phase == phase:
                continue

            lead.x_evie_phase = phase
            lead._evie_notify_phase(phase)

    def _evie_notify_phase(self, phase):
        """Send the translated phase to Evie; schedule an activity on failure."""
        self.ensure_one()
        payload = {
            'capsule_id': self.x_evie_capsule_id or None,
            'odoo_lead_id': self.id,
            'phase': phase,
            'stage_id': self.stage_id.id,
        }
        ok, detail = self.env['evie.webhook'].post('/stage-change', payload)
        if not ok and detail != 'not_configured':
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=self.user_id.id or self.env.user.id,
                note=_("Evie: notifying the phase change to '%s' failed (%s). "
                       "Evie may be out of sync for this record.") % (phase, detail),
            )
