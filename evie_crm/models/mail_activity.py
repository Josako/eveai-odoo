"""Evie anchor fields and notification hooks on mail.activity.

The ``x_evie_`` fields are the anchor contract with the Evie platform:

* ``x_evie_capsule_id`` — the Evie Data Capsule (CRM_ACTIVITY) this activity
  is linked to (source-of-truth coupling)
* ``x_evie_activity_type`` — the stable Evie activity-type key (Evie is
  master over the type vocabulary; ``activity_type_id`` is the Odoo-side
  presentation resolved via ``evie.activity_type_map``)
* ``x_evie_last_synced`` — last push-sync timestamp written by Evie
  (display-only metadata, like on crm.lead; excluded from payload hashes)

``evie_notify_upsert`` is called by the ``[AUTO] Evie: activity upsert``
automation rules (create / write / archive). The event is a hint only —
Evie reads the record fresh (including archived, i.e. done, activities) and
reconciles value-based.

``evie_notify_unlinked`` is called by the ``[AUTO] Evie: activity deleted``
automation rule (Odoo's cancel is a true unlink). Because the record is gone
afterwards, this event carries the identification with it: remote id plus
the anchor when present.
"""

import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: Context flag set by Evie's own writes so the automation rules do not
#: echo Evie-originated activity changes back to Evie.
EVIE_ACTIVITY_SYNC_CONTEXT_KEY = 'evie_skip_activity_event'


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    x_evie_capsule_id = fields.Char(
        string='Evie Capsule ID',
        index=True,
        copy=False,
        readonly=True,
        help="ID of the linked Evie CRM_ACTIVITY Data Capsule "
             "(source-of-truth coupling).",
    )
    x_evie_activity_type = fields.Char(
        string='Evie Activity Type',
        copy=False,
        readonly=True,
        help="Stable Evie activity-type key (Evie is master over the type "
             "vocabulary; activity_type_id is the Odoo presentation).",
    )
    x_evie_last_synced = fields.Datetime(
        string='Evie Last Synced',
        copy=False,
        readonly=True,
        help="Timestamp of the last Evie → Odoo sync for this record "
             "(odoo-evie-form-branding — same anchor as on crm.lead).",
    )
    x_evie_outcome = fields.Selection(
        string='Evie Outcome',
        selection='_selection_evie_outcome',
        copy=False,
        help="Optional outcome of this activity (add-activity-sequences). "
             "Set it before marking the activity done: the stable key syncs "
             "to Evie with the completion and drives sequence branching. "
             "Informational for Odoo — it does not alter Odoo behaviour.",
    )

    # Proposal content (sync-activity-proposal-to-odoo): Evie-master,
    # read-only in Odoo. The specialist's draft and the rep-approved text
    # are shown as two separate fields so the rep can see both what the
    # specialist proposed and what was finally approved.
    x_evie_proposed_content = fields.Html(
        string='Evie Proposal (specialist draft)',
        copy=False,
        readonly=True,
        sanitize=True,
        help="Specialist-drafted proposal for this activity (synced from "
             "Evie, read-only). The original draft — kept as the baseline "
             "when the approved text differs.",
    )
    # Mirrored (direction 'both' in mapping 1.2.0): the rep edits the final
    # text here — Odoo is the rep's playground — and the edit syncs back
    # to the capsule's final_content (html_to_markdown inbound). The
    # upsert automation watches this field, so edits notify Evie directly.
    x_evie_final_content = fields.Html(
        string='Evie Proposal (final)',
        copy=False,
        sanitize=True,
        help="The proposal as approved or edited by the rep. Editable: "
             "changes sync back to Evie. This is the text to use.",
    )

    # Action feedback (sync-activity-proposal-to-odoo): mirrors the lead's
    # x_evie_action_status/x_evie_action_message — the run lifecycle of the
    # activity's Evie actions (e.g. GENERATING while a proposal is being
    # drafted). x_evie_action_status doubles as the binding field for the
    # evie_actions widget on the activity form.
    x_evie_action_status = fields.Char(
        string='Evie Action Status',
        copy=False,
        readonly=True,
        help="Lifecycle of the running/last Evie action on this activity "
             "(e.g. GENERATING); synced from Evie, read-only.",
    )
    x_evie_action_message = fields.Text(
        string='Evie Action Message',
        copy=False,
        readonly=True,
        help="Feedback message of the running/last Evie action on this "
             "activity; synced from Evie, read-only.",
    )

    def _selection_evie_outcome(self):
        """Outcome options from the evie.activity_outcome module data.

        Dynamic selection so tenants can relabel/deactivate outcomes;
        the stored value is always the stable key.
        """
        outcomes = self.env['evie.activity_outcome'].sudo().search([])
        return [(o.key, o.name) for o in outcomes]

    def action_evie_open(self, kind, reference):
        """Open the linked Evie entity in a new browser tab.

        Activity-side counterpart of ``crm.lead.action_evie_open`` (the
        ``evie_link`` widget on the activity form calls it on this
        model). Only ``capsule`` is a valid kind here: the capsule is the
        activity's own anchor.
        """
        self.ensure_one()
        if kind != 'capsule':
            raise UserError(_("Unknown Evie reference type '%s'.") % kind)
        if not reference:
            raise UserError(_("No Evie capsule is linked to this activity yet."))

        user = self.env.user
        ok, data = self.env['evie.webhook'].post_for_json('/view-token', {
            'kind': 'capsule',
            'capsule_id': int(reference),
            'user': {'name': user.name, 'email': user.email},
        })
        if not ok:
            raise UserError(_("Could not open the Evie capsule (%s).") % (data,))

        return {
            'type': 'ir.actions.act_url',
            'url': data['view_url'],
            'target': 'new',
        }

    def evie_notify_upsert(self):
        """Notify Evie of an activity create / write / done (archive).

        Called by the ``[AUTO] Evie: activity upsert`` automation rules.
        Hint only — Evie reads the record fresh with ``active_test: False``
        so done (archived) activities are found, including their feedback.
        No-op for writes carrying the echo-guard context and for activities
        not linked to a CRM lead.
        """
        if self.env.context.get(EVIE_ACTIVITY_SYNC_CONTEXT_KEY):
            return

        leads = self.env['crm.lead']
        for activity in self:
            if activity.res_model != 'crm.lead' or not activity.res_id:
                continue
            payload = {
                'odoo_activity_id': activity.id,
                'capsule_id': activity.x_evie_capsule_id or None,
                'odoo_lead_id': activity.res_id,
            }
            ok, detail = self.env['evie.webhook'].post('/activity-upsert', payload)
            if not ok and detail != 'not_configured':
                leads.browse(activity.res_id).activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=activity.user_id.id or self.env.user.id,
                    note=_("Evie: notifying the activity change failed (%s). "
                           "Evie may be out of sync for this activity.") % detail,
                )

    def evie_notify_unlinked(self):
        """Notify Evie that activities are about to be unlinked (cancel).

        Called by the ``[AUTO] Evie: activity deleted`` automation rule
        (trigger ``on_unlink`` — records are still readable here, gone
        afterwards, so the event carries the identification with it).
        """
        if self.env.context.get(EVIE_ACTIVITY_SYNC_CONTEXT_KEY):
            return

        leads = self.env['crm.lead']
        for activity in self:
            if activity.res_model != 'crm.lead':
                continue
            payload = {
                'model': 'mail.activity',
                'remote_id': activity.id,
                'capsule_id': activity.x_evie_capsule_id or None,
            }
            ok, detail = self.env['evie.webhook'].post('/record-deleted', payload)
            if not ok and detail != 'not_configured':
                # The activity is being deleted; anchor the warning on the lead.
                lead = leads.browse(activity.res_id).exists()
                if lead:
                    lead.activity_schedule(
                        'mail.mail_activity_data_todo',
                        user_id=lead.user_id.id or self.env.user.id,
                        note=_("Evie: notifying the activity deletion failed (%s). "
                               "Evie may keep a cancelled activity as open.") % detail,
                    )
