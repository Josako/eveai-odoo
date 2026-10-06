"""Mirror model for MEETING_OBJECTIVE capsules
(add-odoo-meeting-library-sync).

One objective instance on a meeting plan. Content fields and
``rep_note`` are shared (``both`` — the rep manages the plan from
Odoo); the system-written fields (``origin``, ``case_questions``, the
outcome distillate) are read-only (Evie-master, agent-written). The plan
link travels on this side (``plan_id``): an inline create on the plan's
objective list carries it inbound as an AD_HOC instance; every later
local change is refused by the guard.
"""

from odoo import _, _lt, fields, models

from .objective_template import OBJECTIVE_TYPE_SELECTION, PRIORITY_SELECTION

ORIGIN_SELECTION = [
    ('TEMPLATE', _lt('From a template')),
    ('AD_HOC', _lt('Ad-hoc')),
    ('CARRY_OVER', _lt('Carried over')),
    ('SUGGESTED', _lt('Suggested')),
]

ASSESSMENT_STATUS_SELECTION = [
    ('ACHIEVED', _lt('Achieved')),
    ('PARTIAL', _lt('Partially achieved')),
    ('NOT_ADDRESSED', _lt('Not addressed')),
    ('BLOCKED', _lt('Blocked')),
    ('NOT_APPLICABLE', _lt('Not applicable')),
]


class MeetingObjective(models.Model):
    _name = 'meeting.objective'
    _description = 'Evie Meeting Objective'
    _inherit = ['evie.capsule.link', 'evie.meeting.membership.guard',
                'mail.thread']
    _order = 'plan_id, id'

    #: Locally creatable (ad-hoc objectives on a plan); the record
    #: starts at sync_state 'pending' (the mixin default).
    _evie_local_create = True

    # --- Shared content (both) ---
    name = fields.Char(string='Label', required=True, tracking=True)
    objective_type = fields.Selection(
        OBJECTIVE_TYPE_SELECTION, string='Objective Type',
        required=True, tracking=True)
    intent = fields.Text(string='Intent', required=True)
    success_criterion = fields.Text(string='Success Criterion', required=True)
    guiding_questions = fields.Text(
        string='Guiding Questions', help='One per line.')
    dimensions = fields.Text(
        string='Dimensions', help='Canonical tags, one per line.')
    priority = fields.Selection(
        PRIORITY_SELECTION, string='Priority', default='MEDIUM', tracking=True)
    rep_note = fields.Text(string='Rep Note')
    context_note = fields.Text(string='Context Note')

    # --- System-written (out: agents own these — read-only) ---
    origin = fields.Selection(
        ORIGIN_SELECTION, string='Origin', readonly=True)
    case_questions = fields.Text(
        string='Case Questions', readonly=True,
        help='Case-specific questions from the preparation agent.')
    carried_from_assessment_id = fields.Char(
        string='Carried From Assessment', readonly=True)
    assessment_status = fields.Selection(
        ASSESSMENT_STATUS_SELECTION, string='Assessment', readonly=True)
    assessment_findings = fields.Text(
        string='Assessment Findings', readonly=True)
    follow_up = fields.Text(string='Follow Up', readonly=True)

    # --- Membership (member side; guarded — see the module guard) ---
    plan_id = fields.Many2one(
        'meeting.plan', string='Meeting Plan', required=True,
        index=True, ondelete='restrict', readonly=True)

    active = fields.Boolean(default=True)

    def write(self, vals):
        self._check_member_link_write(vals, 'plan_id', _('meeting plan'))
        return super().write(vals)
