"""Evie Meetings smart button on the lead: every Meeting and Call activity
with a meeting window, planned and done, in one searchable list."""

from odoo import _, fields, models

from .mail_activity import MEETING_CATEGORIES


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    x_evie_meeting_count = fields.Integer(
        string='Evie Meetings', compute='_compute_x_evie_meeting_count')

    def _evie_meeting_domain(self):
        return [
            ('res_model', '=', 'crm.lead'),
            ('res_id', 'in', self.ids),
            ('activity_type_id.category', 'in', MEETING_CATEGORIES),
            ('x_evie_capsule_id', '!=', False),
        ]

    def _compute_x_evie_meeting_count(self):
        counts = dict(
            self.env['mail.activity'].with_context(active_test=False)._read_group(
                self._evie_meeting_domain(), ['res_id'], ['__count'])
        ) if self.ids else {}
        for lead in self:
            lead.x_evie_meeting_count = counts.get(lead.id, 0)

    def action_evie_meetings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Evie Meetings'),
            'res_model': 'mail.activity',
            'view_mode': 'list',
            'views': [(self.env.ref('evie_meetings.mail_activity_view_list_evie_meetings').id, 'list')],
            'search_view_id': self.env.ref('evie_meetings.mail_activity_view_search_evie_meetings').id,
            'domain': self._evie_meeting_domain(),
            'context': {'active_test': False, 'create': False},
        }
