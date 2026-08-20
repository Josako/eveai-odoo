"""Evie anchor fields and notification hooks on mail.activity.

The ``x_evie_`` fields are the anchor contract with the Evie platform:

* ``x_evie_capsule_id`` — the Evie Data Capsule (CRM_ACTIVITY) this activity
  is linked to (source-of-truth coupling)
* ``x_evie_activity_type`` — the stable Evie activity-type key (Evie is
  master over the type vocabulary; ``activity_type_id`` is the Odoo-side
  presentation resolved via ``evie.activity_type_map``)

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
