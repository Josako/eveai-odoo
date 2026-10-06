"""Evie morning brief in Odoo (odoo-native-evie-surfaces, feature 1).

What the rep needs today, from Odoo itself: today's meetings, activities
due, Evie drafts waiting for review and hot leads. Evie's own to-dos, sync
issues and captures stay in the Evie admin brief: for a rep in Odoo the
to-do list is their activities, which Evie syncs.

The brief pops up once per local day (remembered on the user, so not again
on another device) when there is something to show; the sun button (bottom
right of the page) and the daily digest notification reopen it any time.
"""

from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.tools import format_date

from odoo.addons.evie_notifications.rules import (
    HOT_LEAD_SCORE,
    MEETING_CATEGORIES,
    brief_due,
)

SECTION_LIMIT = 6


class EvieBrief(models.AbstractModel):
    _name = 'evie.brief'
    _description = 'Evie Morning Brief'

    @api.model
    def get_brief(self, auto=False):
        """Today's brief. With ``auto`` (on Odoo load) only once per local
        day and only when there is something to show."""
        user = self.env.user
        tz = pytz.timezone(user.tz or 'UTC')
        local_now = fields.Datetime.context_timestamp(self.with_context(tz=tz.zone), fields.Datetime.now())
        today = local_now.date()
        if auto:
            if not brief_due(local_now.hour, user.x_evie_brief_seen_on, today):
                return {'show': False}
            user.sudo().x_evie_brief_seen_on = today
        sections = [section for section in (
            self._evie_meetings(user, today, tz),
            self._evie_activities_due(user, today),
            self._evie_drafts(user),
            self._evie_hot_leads(user),
        ) if section['count']]
        count = sum(section['count'] for section in sections)
        return {
            'show': bool(count) or not auto,
            'brief': {
                'greeting_name': (user.name or '').split(' ')[0],
                'date': fields.Date.to_string(today),
                'sections': sections,
                'count': count,
            },
        }

    @api.model
    def action_open_item(self, model, res_id):
        if model not in self.env:
            return False
        return self.env['evie.notification']._evie_record_action(self.env[model].browse(int(res_id)))

    # ------------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------------

    def _evie_meetings(self, user, today, tz):
        """Calendar events I attend today, plus Meeting / Call activities due
        today; an event with my meeting activity opens the meeting window."""
        start = tz.localize(datetime.combine(today, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        events = self.env['calendar.event'].search([
            ('partner_ids', 'in', user.partner_id.ids),
            ('start', '<', start + timedelta(days=1)),
            ('stop', '>=', start),
        ], order='start')
        activities = self.env['mail.activity'].search([
            ('user_id', '=', user.id),
            ('activity_category', 'in', MEETING_CATEGORIES),
            ('date_deadline', '=', today),
        ])
        activity_by_event = {a.calendar_event_id.id: a for a in activities if a.calendar_event_id}
        items = []
        for event in events:
            when = _("All day") if event.allday else pytz.utc.localize(event.start).astimezone(tz).strftime('%H:%M')
            target = activity_by_event.get(event.id) or event
            items.append(self._evie_item(target, event.name, when, event.location))
        for activity in activities.filtered(lambda a: a.calendar_event_id not in events):
            items.append(self._evie_activity_item(activity, today))
        return self._evie_section(
            'meetings', _("Today's meetings"), 'fa-calendar', items, len(items),
            more=('calendar.action_calendar_event', _("Open my calendar")))

    def _evie_activities_due(self, user, today):
        """Overdue and due-today activities (today's meetings are above)."""
        domain = [
            ('user_id', '=', user.id),
            ('date_deadline', '<=', today),
            '|', ('activity_category', 'not in', MEETING_CATEGORIES), ('date_deadline', '<', today),
        ]
        Activity = self.env['mail.activity']
        activities = Activity.search(domain, order='date_deadline, id', limit=SECTION_LIMIT)
        return self._evie_section(
            'activities', _("Activities due"), 'fa-clock-o',
            [self._evie_activity_item(a, today) for a in activities], Activity.search_count(domain),
            more=('mail.mail_activity_action_my', _("Open my activities")))

    def _evie_drafts(self, user):
        """Activities with an Evie proposal the rep has not approved yet."""
        domain = [
            ('user_id', '=', user.id),
            ('x_evie_proposed_content', '!=', False),
            ('x_evie_final_content', '=', False),
        ]
        Activity = self.env['mail.activity']
        activities = Activity.search(domain, order='date_deadline, id', limit=SECTION_LIMIT)
        return self._evie_section(
            'drafts', _("Evie drafts to review"), 'fa-pencil-square-o',
            [self._evie_activity_item(a) for a in activities], Activity.search_count(domain))

    def _evie_hot_leads(self, user):
        domain = [
            ('user_id', '=', user.id),
            ('x_evie_qualification_score', '>=', HOT_LEAD_SCORE),
            ('stage_id.is_won', '=', False),
        ]
        Lead = self.env['crm.lead']
        leads = Lead.search(domain, order='x_evie_qualification_score desc, id desc', limit=SECTION_LIMIT)
        items = [
            self._evie_item(lead, lead.name, _("Score %s", lead.x_evie_qualification_score),
                            lead.stage_id.name, lead.partner_name or lead.partner_id.name)
            for lead in leads
        ]
        return self._evie_section(
            'leads', _("Hot leads"), 'fa-bolt', items, Lead.search_count(domain),
            more=('crm.crm_lead_action_pipeline', _("Open my pipeline")))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _evie_section(key, title, icon, items, count, more=None):
        return {
            'key': key, 'title': title, 'icon': icon, 'items': items, 'count': count,
            'more': more[0] if more else False, 'more_label': more[1] if more else '',
        }

    @staticmethod
    def _evie_item(record, title, *meta, due='', overdue=False, key=None):
        return {
            'key': key or f'{record._name}-{record.id}',
            'model': record._name,
            'id': record.id,
            'title': title or record.display_name,
            'meta': [str(value) for value in meta if value],
            'due': due,
            'overdue': overdue,
        }

    def _evie_activity_item(self, activity, today=None):
        """Evie-linked meetings open their meeting window (the activity
        itself), other activities the record they are on, like the activity
        notifications."""
        record = activity._evie_related_record()
        meeting = activity.activity_category in MEETING_CATEGORIES and activity.x_evie_capsule_id
        target = activity if meeting or not record else record
        due, overdue = '', False
        if today and activity.date_deadline:
            overdue = activity.date_deadline < today
            due = (_("Overdue since %s", format_date(self.env, activity.date_deadline))
                   if overdue else _("Due today"))
        return self._evie_item(target, activity._evie_label(), record and record.display_name,
                               due=due, overdue=overdue, key=f'mail.activity-{activity.id}')
