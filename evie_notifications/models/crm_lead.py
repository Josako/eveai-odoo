"""Lead triggers for the Evie notification center.

The lead owner (salesperson) hears about: being assigned a lead, stage
moves / wins on their lead, their lead being marked lost, the Evie
qualification score crossing the hot threshold and Evie actions finishing
or failing. ``evie.notification._notify`` drops the author of the change, so
people never get notified about their own edits.
"""

from odoo import _, api, models

from odoo.addons.evie_notifications.rules import (
    ACTION_FINISHED_STATUSES,
    crossed_hot_threshold,
    is_muted,
    lead_change_events,
)

_WATCHED_FIELDS = ('user_id', 'stage_id', 'active', 'x_evie_qualification_score')


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create(vals_list)
        if not is_muted(self.env.context):
            notifications = self.env['evie.notification']
            for lead in leads.filtered('user_id'):
                notifications._notify(
                    lead.user_id, _("New lead assigned to you"), body=lead.display_name,
                    record=lead, kind='lead',
                )
        return leads

    def write(self, vals):
        if is_muted(self.env.context) or not any(f in vals for f in _WATCHED_FIELDS):
            return super().write(vals)

        before = {
            lead.id: {
                'user': lead.user_id.id,
                'stage': lead.stage_id.id,
                'active': lead.active,
                'score': lead.x_evie_qualification_score,
            }
            for lead in self
        }
        result = super().write(vals)
        for lead in self:
            lead._evie_notify_changes(before.get(lead.id))
        return result

    def _evie_notify_changes(self, old):
        self.ensure_one()
        if not old or not self.user_id:
            return
        notifications = self.env['evie.notification']
        owner = self.user_id
        name = self.display_name

        for event in lead_change_events(old['user'], owner.id, old['stage'], self.stage_id.id):
            if event == 'assigned':
                notifications._notify(
                    owner, _("New lead assigned to you"), body=name,
                    record=self, kind='lead',
                )
            elif self.stage_id.is_won:
                notifications._notify(
                    owner, _("Lead won"), body=name,
                    record=self, kind='lead', tone='success',
                )
            else:
                notifications._notify(
                    owner, _("Lead moved to %s", self.stage_id.name), body=name,
                    record=self, kind='lead',
                )

        if old['active'] and not self.active:
            notifications._notify(
                owner, _("Lead marked as lost"), body=name,
                record=self, kind='lead', tone='warning',
            )

        if crossed_hot_threshold(old['score'], self.x_evie_qualification_score):
            notifications._notify(
                owner, _("Hot lead"),
                body=_("%(name)s scored %(score)s", name=name,
                       score=self.x_evie_qualification_score),
                record=self, kind='evie', tone='success',
            )

    def evie_notify_action_completed(self):
        super().evie_notify_action_completed()
        notifications = self.env['evie.notification']
        for lead in self.filtered('user_id'):
            status = lead.x_evie_action_status
            if status not in ACTION_FINISHED_STATUSES:
                continue
            done = status == 'DONE'
            notifications._notify(
                lead.user_id,
                _("Evie finished an action") if done else _("Evie action failed"),
                body=lead.x_evie_action_message or lead.display_name,
                record=lead, kind='evie', tone='success' if done else 'danger',
            )
