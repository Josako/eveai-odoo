"""Mirror model for MEETING_PLAN capsules (add-odoo-meeting-library-sync).

The plan for one meeting activity. Plans are composed in Evie (the
compose endpoint, called from the meeting window) — never created or
re-anchored in Odoo — so the model is not locally creatable and the
core fields are read-only; only ``notes`` is shared (``both``). A
SUPERSEDED plan syncs archived, keeping at most one active plan mirror
per activity (enforced by the constraint). Objectives are the pure
inverse of the member side.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Selection labels must be plain strings (Odoo translates them itself).
PLAN_SOURCE_SELECTION = [
    ('USER', 'Planned by the rep'),
    ('SUGGESTED_ACCEPTED', 'System proposal accepted'),
    ('INFERRED_POST_HOC', 'Inferred afterwards'),
]

PLAN_STATUS_SELECTION = [
    ('DRAFT', 'Draft'),
    ('CONFIRMED', 'Confirmed'),
    ('SUPERSEDED', 'Superseded'),
]


class MeetingPlan(models.Model):
    _name = 'meeting.plan'
    _description = 'Evie Meeting Plan'
    _inherit = ['evie.capsule.link', 'mail.thread']
    _order = 'write_date desc'

    # --- Plan core (out: Evie-master, read-only) ---
    source = fields.Selection(
        PLAN_SOURCE_SELECTION, string='Source', readonly=True, tracking=True)
    status = fields.Selection(
        PLAN_STATUS_SELECTION, string='Status', readonly=True, tracking=True)
    meeting_kind = fields.Char(
        string='Meeting Kind', readonly=True,
        help='Stable MEETING_KIND key, snapshotted at planning time.')
    activity_id = fields.Many2one(
        'mail.activity', string='Activity', index=True, readonly=True,
        ondelete='set null',
        help='The meeting activity this plan belongs to.')

    # --- Shared (both) ---
    notes = fields.Text(string='Notes')

    # --- Objectives: the pure inverse of the member side. Not readonly
    # in the view so reps can inline-create ad-hoc objectives; linking
    # or removing existing lines is refused by the member-side guard. ---
    objective_ids = fields.One2many(
        'meeting.objective', 'plan_id', string='Objectives')

    active = fields.Boolean(default=True)

    def action_new_objective(self):
        """Create an ad-hoc objective directly on this plan: a genuine
        create carrying the plan link at creation — lands in Evie as an
        AD_HOC instance."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('New ad-hoc objective'),
            'res_model': 'meeting.objective',
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_plan_id': self.id},
        }

    @api.depends('source')
    def _compute_display_name(self):
        source_labels = dict(PLAN_SOURCE_SELECTION)
        for plan in self:
            label = source_labels.get(plan.source, plan.source or '?')
            plan.display_name = _('Meeting plan (%s)') % label

    @api.constrains('activity_id', 'active')
    def _check_single_active_plan_per_activity(self):
        """At most one ACTIVE plan mirror per activity (Evie keeps the
        same invariant: at most one current DRAFT/CONFIRMED plan)."""
        for plan in self:
            if not plan.active or not plan.activity_id:
                continue
            others = self.search_count([
                ('activity_id', '=', plan.activity_id.id),
                ('active', '=', True),
                ('id', '!=', plan.id),
            ])
            if others:
                raise ValidationError(_(
                    'This activity already has an active meeting plan. '
                    'A meeting has at most one current plan.'
                ))
