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

from odoo.addons.evie_base.consts import EVIE_PHASE_SELECTION

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
    x_evie_phase = fields.Selection(
        selection=EVIE_PHASE_SELECTION,
        string='Evie Phase',
        index=True,
        copy=False,
        tracking=True,
        help="Stable Evie funnel phase. Written by every Evie sync, kept "
             "consistent when the stage changes, and directly editable — "
             "edits are notified to Evie via the stage-change channel.",
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

            # Echo-guard: without the flag this write would retrigger the
            # on_write(x_evie_phase) automation and double-notify Evie.
            lead.with_context(**{EVIE_SYNC_CONTEXT_KEY: True}) \
                .write({'x_evie_phase': phase})
            lead._evie_notify_phase(phase)

    def evie_notify_phase_change(self):
        """Notify Evie of a direct edit of ``x_evie_phase``.

        Called by the ``[AUTO] Evie: phase edited`` automation rule. Uses the
        same stage-change channel as stage-driven changes; Evie applies the
        (already stable) phase value-based. No-op for writes carrying the
        echo-guard context (Evie sync writes and the stage→phase rule above).
        """
        if self.env.context.get(EVIE_SYNC_CONTEXT_KEY):
            return

        for lead in self:
            if not lead.x_evie_phase:
                continue
            lead._evie_notify_phase(lead.x_evie_phase)

    def evie_notify_upsert(self):
        """Notify Evie of a lead create / mirrored-field write / archive.

        Called by the ``[AUTO] Evie: lead upsert`` automation rules. The
        event is a hint only — Evie reads the record fresh (including the
        ``active`` flag, which drives the capsule status) and reconciles
        value-based. No-op for writes carrying the echo-guard context.
        """
        if self.env.context.get(EVIE_SYNC_CONTEXT_KEY):
            return

        for lead in self:
            payload = {
                'capsule_id': lead.x_evie_capsule_id or None,
                'odoo_lead_id': lead.id,
            }
            ok, detail = self.env['evie.webhook'].post('/lead-upsert', payload)
            if not ok and detail != 'not_configured':
                lead.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=lead.user_id.id or self.env.user.id,
                    note=_("Evie: notifying the lead change failed (%s). "
                           "Evie may be out of sync for this record.") % detail,
                )

    def _merge_opportunity(self, *args, **kwargs):
        """Report the merge to Evie after the records have merged.

        Overrides the private worker so every entry path is covered (the
        public ``merge_opportunity`` and dedup flows both delegate here).

        The merge itself is pure Odoo: the surviving record (highest
        confidence level) keeps/absorbs field values per Odoo's merge
        strategies — head value wins per field, description concatenated,
        address taken as a whole from the most complete record, ``x_evie_*``
        not merged (the head's anchor survives) — and the merged-away
        records are unlinked. Evie reconciles the survivor and
        administratively marks the losers' capsules (DELETED + merge
        lineage) — Evie never re-merges field values. A failed notification
        never blocks or rolls back the merge.
        """
        merged_away_ids = set(self.ids)
        survivor = super()._merge_opportunity(*args, **kwargs)

        if survivor:
            merged_away_ids.discard(survivor.id)
        if not survivor or not merged_away_ids:
            return survivor

        ok, detail = self.env['evie.webhook'].post('/leads-merged', {
            'survivor_odoo_lead_id': survivor.id,
            'merged_odoo_lead_ids': sorted(merged_away_ids),
        })
        if not ok and detail != 'not_configured':
            survivor.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=survivor.user_id.id or self.env.user.id,
                note=_("Evie: reporting the merge of records %s failed (%s). "
                       "Evie may be out of sync for the merged records.")
                % (sorted(merged_away_ids), detail),
            )
        return survivor

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
