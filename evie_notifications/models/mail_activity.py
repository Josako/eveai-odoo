"""Activity triggers for the Evie notification center.

Works on activities of every model (leads, quotes, contacts, ...):

* the assignee hears about an activity assigned to them (create and
  reassignment)
* the owner of the related record (its ``user_id``) hears when someone
  else completes an activity on it

Clicking the notification opens the related record, where the activity
lives. The daily "due today / overdue" digest is a cron on
``evie.notification``.
"""

from odoo import _, api, models
from odoo.tools import format_date

from odoo.addons.evie_notifications.rules import is_muted


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    @api.model_create_multi
    def create(self, vals_list):
        activities = super().create(vals_list)
        if not is_muted(self.env.context):
            activities.filtered('user_id')._evie_notify_assigned()
        return activities

    def write(self, vals):
        if 'user_id' not in vals or is_muted(self.env.context):
            return super().write(vals)
        before = {activity.id: activity.user_id.id for activity in self}
        result = super().write(vals)
        self.filtered(
            lambda a: a.user_id and a.user_id.id != before.get(a.id)
        )._evie_notify_assigned()
        return result

    def _action_done(self, feedback=False, attachment_ids=None):
        # Done activities are archived by super(): collect what we need first.
        pending = []
        if not is_muted(self.env.context):
            for activity in self:
                record = activity._evie_related_record()
                owner = record.user_id if record and activity._evie_has_owner(record) else None
                if owner:
                    pending.append((owner, record, activity._evie_label()))
        result = super()._action_done(feedback=feedback, attachment_ids=attachment_ids)

        notifications = self.env['evie.notification']
        for owner, record, label in pending:
            notifications._notify(
                owner,
                _("%(user)s completed an activity", user=self.env.user.name),
                body=_("%(activity)s on %(record)s", activity=label, record=record.display_name),
                record=record, kind='activity', tone='success',
            )
        return result

    def _evie_notify_assigned(self):
        notifications = self.env['evie.notification']
        for activity in self:
            record = activity._evie_related_record()
            body = activity._evie_label()
            if record:
                body = _("%(activity)s on %(record)s", activity=body, record=record.display_name)
            if activity.date_deadline:
                body = _("%(text)s, due %(date)s", text=body,
                         date=format_date(self.env, activity.date_deadline))
            notifications._notify(
                activity.user_id, _("New activity assigned to you"), body=body,
                record=record or None, kind='activity',
            )

    def _evie_related_record(self):
        """The document the activity is attached to, or ``None``."""
        self.ensure_one()
        if not self.res_model or not self.res_id or self.res_model not in self.env:
            return None
        return self.env[self.res_model].browse(self.res_id).exists() or None

    @staticmethod
    def _evie_has_owner(record):
        field = record._fields.get('user_id')
        return field is not None and field.type == 'many2one' and field.comodel_name == 'res.users'

    def _evie_label(self):
        self.ensure_one()
        return self.summary or self.activity_type_id.name or _("Activity")
