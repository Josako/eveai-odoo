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
link on the form (the ``evie_link`` field widgets; the earlier stat buttons
were removed in 19.0.1.4.0 — the Evie tab is the single place). New Evie
reference types only need a new entry in ``EVIE_OPEN_KINDS``
(extend-odoo-lead-sync-2).
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL

from odoo.addons.evie_base.consts import EVIE_PHASE_SELECTION, EVIE_PHASES

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
        # Kanban expansion: one column per phase, in definition (= funnel)
        # order, including empty phases.
        group_expand=True,
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
        tracking=True,
        help="LinkedIn profile or company page of the lead. Mirrored with "
             "Evie (both directions, last-write-wins): rep edits are "
             "tracked and sync back to the capsule.",
    )
    # Mirrored language (crm-sync-polish): OUR field, plain stored — the
    # native lang_id is a computed partner-derived field and stays out of
    # the sync. Editable; translations run via evie.language_map.
    x_evie_language = fields.Many2one(
        'res.lang',
        string='Evie Language',
        copy=False,
        tracking=True,
        help="Language of the lead, mirrored with Evie both directions via "
             "the Evie language mapping (Configuration → Evie). Empty means "
             "unset — the sync never clears a language.",
    )
    # View-domain helper for x_evie_language: the dropdown offers exactly
    # the languages present in evie.language_map (active rows), including
    # not-yet-activated res.lang records (the view sets active_test=False).
    x_evie_mapped_language_ids = fields.Many2many(
        'res.lang',
        compute='_compute_x_evie_mapped_language_ids',
        compute_sudo=True,
        string='Mappable Evie Languages',
    )

    def _compute_x_evie_mapped_language_ids(self):
        langs = self.env['evie.language_map'].search([]).mapped('odoo_lang_id')
        for lead in self:
            lead.x_evie_mapped_language_ids = langs
    x_evie_qualification_score = fields.Integer(
        string='Evie Qualification Score',
        copy=False,
        readonly=True,
        tracking=True,
        aggregator='avg',
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

    # Action lifecycle (19.0.1.4.0, odoo-capsule-actions). Written by the
    # Evie → Odoo sync; the evie_actions widget renders the running state,
    # the completion automation posts the chatter message.
    x_evie_action_status = fields.Char(
        string='Evie Action Status',
        copy=False,
        readonly=True,
        tracking=True,
        help="Lifecycle of the running/last Evie background action "
             "(RESEARCHING/DONE/FAILED).",
    )
    x_evie_action_message = fields.Text(
        string='Evie Action Message',
        copy=False,
        readonly=True,
        help="Result message of the last finished Evie action.",
    )

    # Lead pipeline board (19.0.1.5.0, odoo-lead-pipeline-board). Colour index
    # for the kanban card strip and score badge, derived from the
    # qualification score. Non-stored: purely presentational. Note that an
    # Integer field reads 0 when unset, so a score of 0 is treated as
    # "no score yet" (no colour).
    x_evie_score_color = fields.Integer(
        string='Evie Score Colour',
        compute='_compute_x_evie_score_color',
        store=False,
        help="Kanban colour index derived from the qualification score "
             "(red < 40, orange 40-69, green >= 70). A score of 0 means "
             "'no score yet' and renders uncoloured.",
    )

    @api.model
    def _read_group_orderby(self, order, groupby_terms, query):
        """Order x_evie_phase groups by funnel position, not alphabetically.

        read_group orders selection groupbys by raw column value
        (alphabetical), which scrambles the pipeline in graph/pivot/list
        views — the kanban is covered by group_expand. A CASE over the
        stable phase order fixes the default order; explicit order strings
        are left untouched. Empty/unknown phases sort last (ELSE).
        """
        if not order and 'x_evie_phase' in groupby_terms:
            cases = SQL(' ').join(
                SQL('WHEN %s THEN %s', phase, index)
                for index, phase in enumerate(EVIE_PHASES)
            )
            return SQL(
                'CASE %s %s ELSE %s END',
                groupby_terms['x_evie_phase'], cases, len(EVIE_PHASES),
            )
        return super()._read_group_orderby(order, groupby_terms, query)

    @api.depends('x_evie_qualification_score')
    def _compute_x_evie_score_color(self):
        """Map the qualification score to an Odoo kanban colour index."""
        for lead in self:
            score = lead.x_evie_qualification_score
            if not score:
                lead.x_evie_score_color = 0   # no colour (no score yet)
            elif score < 40:
                lead.x_evie_score_color = 1   # red
            elif score < 70:
                lead.x_evie_score_color = 2   # orange
            else:
                lead.x_evie_score_color = 6   # green

    def evie_notify_action_completed(self):
        """Post a chatter message when a synced action run finishes or fails.

        Called by the ``[AUTO] Evie: action completed`` automation rule on
        writes of ``x_evie_action_status``. The outbound sync is hash-diffed,
        so the rule only fires on actual transitions; RESEARCHING writes are
        ignored (no chatter noise while running).
        """
        for lead in self:
            status = lead.x_evie_action_status
            if status not in ('DONE', 'FAILED'):
                continue
            message = lead.x_evie_action_message or ''
            if status == 'DONE':
                body = _("Evie action finished: %s") % message
            else:
                body = _("Evie action failed: %s") % message
            lead.message_post(body=body, subtype_xmlid='mail.mt_note')

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
            'user': {'name': user.name, 'email': user.email, 'id': user.id},
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
