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

``action_evie_open`` is the single dispatcher behind every "open in Evie"
link on the form (stat buttons and ``evie_link`` field widgets). New Evie
reference types only need a new entry in ``EVIE_OPEN_KINDS``
(extend-odoo-lead-sync-2).
"""

import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: Context flag set by Evie's own writes so the automation rule does not
#: echo Evie-originated stage changes back to Evie.
EVIE_SYNC_CONTEXT_KEY = 'evie_skip_phase_event'

#: Evie entity kinds the lead form can open, mapped to the request field the
#: Evie view-token endpoint expects for that kind.
EVIE_OPEN_KINDS = {
    'document': 'document_version_id',
    'capsule': 'capsule_id',
}


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

    # Lead context (19.0.1.1.0, extend-odoo-lead-sync-1). All written by the
    # Evie → Odoo sync; empty document references mean "no research yet".
    x_evie_source = fields.Char(
        string='Evie Source',
        copy=False,
        readonly=True,
        tracking=True,
        help="Lead source in Evie (enum value, as-is).",
    )
    x_evie_linkedin_url = fields.Char(
        string='LinkedIn URL',
        copy=False,
        readonly=True,
        tracking=True,
        help="LinkedIn profile or company page of the lead in Evie.",
    )
    x_evie_qualification_score = fields.Integer(
        string='Evie Qualification Score',
        copy=False,
        readonly=True,
        tracking=True,
        help="Current qualification score (0-100) assigned by Evie lead research.",
    )
    x_evie_report_doc_version_id = fields.Integer(
        string='Evie Report Document Version',
        copy=False,
        readonly=True,
        tracking=True,
        help="Evie document version ID of the latest lead research report.",
    )
    x_evie_rationale_doc_version_id = fields.Integer(
        string='Evie Rationale Document Version',
        copy=False,
        readonly=True,
        tracking=True,
        help="Evie document version ID of the latest qualification rationale.",
    )

    def action_evie_view_report(self):
        """Open the latest research report in Evie (new browser tab)."""
        self.ensure_one()
        return self.action_evie_open('document', self.x_evie_report_doc_version_id)

    def action_evie_view_rationale(self):
        """Open the latest qualification rationale in Evie (new browser tab)."""
        self.ensure_one()
        return self.action_evie_open('document', self.x_evie_rationale_doc_version_id)

    def action_evie_view_capsule(self):
        """Open the linked Data Capsule in Evie (new browser tab)."""
        self.ensure_one()
        return self.action_evie_open('capsule', self.x_evie_capsule_id)

    def action_evie_open(self, kind, reference):
        """Single dispatcher behind every "open in Evie" link on the form.

        Exchanges the integration API key for a short-lived view token for
        the given entity kind and opens the returned view URL in a new
        browser tab. New reference types only need a new entry in
        ``EVIE_OPEN_KINDS``.

        The current Odoo user's identity is sent along so Evie can audit who
        viewed the entity. Failures surface as a visible, non-blocking
        error dialog.
        """
        self.ensure_one()

        request_key = EVIE_OPEN_KINDS.get(kind)
        if not request_key:
            raise UserError(_("Unknown Evie reference type '%s'.") % kind)
        if not reference:
            raise UserError(_("No Evie %s is linked to this lead yet.") % kind)

        user = self.env.user
        ok, data = self.env['evie.webhook'].post_for_json('/view-token', {
            'kind': kind,
            request_key: int(reference),
            'user': {'name': user.name, 'email': user.email},
        })
        if not ok:
            raise UserError(_("Could not open the Evie %s (%s).") % (kind, data))

        return {
            'type': 'ir.actions.act_url',
            'url': data['view_url'],
            'target': 'new',
        }

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
