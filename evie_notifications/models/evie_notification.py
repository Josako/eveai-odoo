"""Evie notification center (odoo-notification-center).

One ``evie.notification`` row per recipient. Producers call ``_notify()``
(or ``_notify_record()`` from an automation rule); the row is stored and
pushed live to the recipient's browser tabs over the Odoo bus, where the
systray bell (``evie_notification_menu.js``) picks it up.

The producer API is private on purpose: public model methods are callable
over RPC by every internal user, which would let anyone send notifications
to anyone.

Users only read their own rows (record rule) and never write them
directly: the bell's actions (mark read, clear) go through the
``systray_*`` / ``mark_*`` / ``dismiss*`` methods below, which scope to the
current user and write with sudo.
"""

import logging
from collections import defaultdict
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from odoo.addons.evie_notifications.rules import (
    digest_due,
    due_digest_counts,
    is_muted,
)

_logger = logging.getLogger(__name__)

#: Bus notification types — keep in sync with evie_notification_service.js.
BUS_NEW = 'evie_notification/new'
BUS_SYNC = 'evie_notification/sync'

#: How many items the bell panel shows per tab.
SYSTRAY_LIMIT = 30
OLDER_LIMIT = 50

RETENTION_PARAM = 'evie_notifications.retention_days'
DEFAULT_RETENTION_DAYS = 90

KIND_SELECTION = [
    ('lead', 'Lead'),
    ('activity', 'Activity'),
    ('evie', 'Evie'),
    ('other', 'Other'),
]
TONE_SELECTION = [
    ('info', 'Info'),
    ('success', 'Success'),
    ('warning', 'Warning'),
    ('danger', 'Danger'),
]


class EvieNotification(models.Model):
    _name = 'evie.notification'
    _description = 'Evie Notification'
    _order = 'create_date desc, id desc'
    _rec_name = 'title'

    user_id = fields.Many2one(
        'res.users', string='Recipient', required=True, index=True,
        ondelete='cascade', readonly=True,
    )
    author_id = fields.Many2one(
        'res.users', string='Triggered by', ondelete='set null', readonly=True,
        help="User whose change caused the notification (empty for "
             "scheduled notifications such as the activity digest).",
    )
    title = fields.Char(required=True, readonly=True)
    body = fields.Text(readonly=True)
    kind = fields.Selection(KIND_SELECTION, required=True, default='other', readonly=True)
    tone = fields.Selection(TONE_SELECTION, required=True, default='info', readonly=True)
    res_model = fields.Char(string='Related Model', index=True, readonly=True)
    res_id = fields.Many2oneReference(
        string='Related Record', model_field='res_model', readonly=True,
    )
    action_xmlid = fields.Char(
        string='Action to open', readonly=True,
        help="Window action opened on click instead of a single record "
             "(e.g. 'My activities' for the digest).",
    )
    is_read = fields.Boolean(string='Read', default=False, index=True, readonly=True)
    read_date = fields.Datetime(readonly=True)
    active = fields.Boolean(
        default=True,
        help="Cleared notifications are archived: they leave the bell's "
             "Recent tab but stay under Older until retention removes them.",
    )
    dedupe_key = fields.Char(
        index=True, readonly=True,
        help="When set, a recipient never gets a second notification with "
             "the same key (e.g. one activity digest per local day).",
    )

    # ------------------------------------------------------------------
    # Producer API
    # ------------------------------------------------------------------

    @api.model
    def _notify(self, users, title, body=None, record=None, kind='other',
               tone='info', action_xmlid=None, dedupe_key=None, author=None):
        """Create notifications for ``users`` and push them live.

        :param users: ``res.users`` recordset of recipients
        :param record: optional related record, opened when the item is clicked
        :param author: the user who caused it; defaults to the current user
            and is never notified. Pass an empty recordset for scheduled
            notifications that have no author.
        :returns: the created ``evie.notification`` records (sudo)
        """
        if is_muted(self.env.context):
            return self.browse()
        author = self.env.user if author is None else author
        recipients = users.sudo().filtered(
            lambda u: u.active and not u.share and u != author)
        if dedupe_key and recipients:
            already = self.sudo().with_context(active_test=False).search([
                ('dedupe_key', '=', dedupe_key),
                ('user_id', 'in', recipients.ids),
            ]).user_id
            recipients -= already
        if not recipients:
            return self.browse()

        vals_list = [{
            'user_id': user.id,
            'author_id': author.id or False,
            'title': title,
            'body': body or False,
            'kind': kind,
            'tone': tone,
            'res_model': record._name if record else False,
            'res_id': record.id if record else False,
            'action_xmlid': action_xmlid or False,
            'dedupe_key': dedupe_key or False,
        } for user in recipients]
        notifications = self.sudo().create(vals_list)
        notifications._evie_push_new()
        return notifications

    @api.model
    def _notify_record(self, record, users=None, title=None, body=None, tone='info'):
        """Entry point for automation rules on any model.

        Example server action (Python code) on a sale order rule::

            env['evie.notification']._notify_record(
                record, title="Quote confirmed", body=record.name)

        Without ``users`` the record's ``user_id`` (salesperson,
        responsible, ...) is notified when the model has one.
        """
        record.ensure_one()
        if users is None:
            field = record._fields.get('user_id')
            owned = getattr(field, 'comodel_name', None) == 'res.users'
            users = record.user_id if owned else self.env['res.users']
        return self._notify(
            users, title or record.display_name, body=body, record=record,
            kind='other', tone=tone,
        )

    # ------------------------------------------------------------------
    # Bell API (called from the systray, scoped to the current user)
    # ------------------------------------------------------------------

    @api.model
    def systray_get(self):
        """Recent (not cleared) notifications plus the unread count."""
        items = self.sudo().search([('user_id', '=', self.env.uid)], limit=SYSTRAY_LIMIT)
        return {
            'items': [item._evie_format() for item in items],
            'unread_count': self._evie_unread_count(self.env.user),
        }

    @api.model
    def systray_get_older(self):
        """Cleared notifications, newest first."""
        items = self.sudo().with_context(active_test=False).search([
            ('user_id', '=', self.env.uid),
            ('active', '=', False),
        ], limit=OLDER_LIMIT)
        return [item._evie_format() for item in items]

    @api.model
    def mark_read(self, ids):
        items = self._evie_own([('id', 'in', ids), ('is_read', '=', False)])
        items._evie_set_read()
        return self._evie_sync(read_ids=items.ids)

    @api.model
    def mark_all_read(self):
        self._evie_own([('is_read', '=', False)])._evie_set_read()
        return self._evie_sync(all_read=True)

    @api.model
    def dismiss(self, ids):
        items = self._evie_own([('id', 'in', ids)])
        items._evie_set_read()
        items.write({'active': False})
        return self._evie_sync(dismissed_ids=items.ids)

    @api.model
    def dismiss_all(self):
        items = self._evie_own([])
        items._evie_set_read()
        items.write({'active': False})
        return self._evie_sync(all_dismissed=True)

    def action_open(self):
        """Mark read and return the action opening the related target.

        Returns ``False`` when there is nothing (left) to open or the user
        cannot read the related record.
        """
        self.ensure_one()
        if self.user_id != self.env.user and not self.env.is_system():
            raise AccessError(_("This notification belongs to another user."))
        if not self.is_read:
            self.sudo()._evie_set_read()
            self._evie_sync(read_ids=self.ids)

        if self.action_xmlid:
            return self.env['ir.actions.actions']._for_xml_id(self.action_xmlid)
        if not (self.res_model and self.res_id) or self.res_model not in self.env:
            return False
        record = self.env[self.res_model].browse(self.res_id).exists()
        if not record:
            return False
        try:
            record.check_access('read')
        except AccessError:
            return False
        if hasattr(record, '_evie_notification_action'):
            action = record._evie_notification_action()
            if action:
                return action
        return {
            'type': 'ir.actions.act_window',
            'res_model': record._name,
            'res_id': record.id,
            'views': [(False, 'form')],
            'target': 'current',
        }

    # ------------------------------------------------------------------
    # Scheduled jobs
    # ------------------------------------------------------------------

    @api.model
    def _cron_activity_digest(self):
        """Once per user per local day: "N overdue, M due today".

        Runs hourly; a user gets the digest in the first run after
        ``DIGEST_HOUR`` in their own timezone (dedupe key per local date).
        """
        horizon = fields.Date.today() + timedelta(days=1)
        activities = self.env['mail.activity'].sudo().search([
            ('date_deadline', '<=', horizon),
            ('user_id', '!=', False),
        ])
        deadlines_by_user = defaultdict(list)
        for activity in activities:
            deadlines_by_user[activity.user_id].append(activity.date_deadline)

        now = fields.Datetime.now()
        no_author = self.env['res.users']
        for user, deadlines in deadlines_by_user.items():
            if user.share or not user.active:
                continue
            local_now = fields.Datetime.context_timestamp(
                self.with_context(tz=user.tz or 'UTC'), now)
            today = local_now.date()
            overdue, due_today = due_digest_counts(deadlines, today)
            if not digest_due(local_now.hour, overdue, due_today):
                continue
            if overdue and due_today:
                body = _("%(overdue)s overdue and %(today)s due today.",
                         overdue=overdue, today=due_today)
            elif overdue:
                body = _("%s overdue.", overdue)
            else:
                body = _("%s due today.", due_today)
            self._notify(
                user, _("Your activities for today"), body=body,
                kind='activity', tone='warning' if overdue else 'info',
                action_xmlid='mail.mail_activity_action_my',
                dedupe_key=f'activity-digest:{today.isoformat()}',
                author=no_author,
            )

    @api.model
    def _cron_cleanup(self):
        """Remove notifications older than the retention period."""
        param = self.env['ir.config_parameter'].sudo().get_param(RETENTION_PARAM)
        try:
            days = int(param) if param else DEFAULT_RETENTION_DAYS
        except ValueError:
            days = DEFAULT_RETENTION_DAYS
        cutoff = fields.Datetime.now() - timedelta(days=max(days, 1))
        old = self.sudo().with_context(active_test=False).search([('create_date', '<', cutoff)])
        if old:
            _logger.info("Evie notifications: removing %s older than %s days", len(old), days)
            old.unlink()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _evie_own(self, domain):
        """The current user's notifications matching ``domain`` (sudo)."""
        return self.sudo().search([('user_id', '=', self.env.uid)] + domain)

    def _evie_set_read(self):
        unread = self.filtered(lambda n: not n.is_read)
        if unread:
            unread.write({'is_read': True, 'read_date': fields.Datetime.now()})

    @api.model
    def _evie_unread_count(self, user):
        return self.sudo().search_count([('user_id', '=', user.id), ('is_read', '=', False)])

    @api.model
    def _evie_sync(self, read_ids=(), dismissed_ids=(), all_read=False, all_dismissed=False):
        """Tell the user's other tabs what changed; returns the new unread count."""
        user = self.env.user
        payload = {
            'unread_count': self._evie_unread_count(user),
            'read_ids': list(read_ids),
            'dismissed_ids': list(dismissed_ids),
            'all_read': all_read,
            'all_dismissed': all_dismissed,
        }
        user.sudo()._bus_send(BUS_SYNC, payload)
        return {'unread_count': payload['unread_count']}

    def _evie_push_new(self):
        unread_by_user = {}
        for notification in self:
            user = notification.user_id
            if user.id not in unread_by_user:
                unread_by_user[user.id] = self._evie_unread_count(user)
            payload = notification._evie_format()
            payload['unread_count'] = unread_by_user[user.id]
            user.sudo()._bus_send(BUS_NEW, payload)

    def _evie_format(self):
        self.ensure_one()
        return {
            'id': self.id,
            'title': self.title,
            'body': self.body or '',
            'kind': self.kind,
            'tone': self.tone,
            'res_model': self.res_model or False,
            'res_id': self.res_id or False,
            'action_xmlid': self.action_xmlid or False,
            'is_read': self.is_read,
            'create_date': fields.Datetime.to_string(self.create_date),
            'author_name': self.author_id.name or '',
        }
