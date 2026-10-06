"""Mirror model for OBJECTIVE_TEMPLATE capsules
(add-odoo-meeting-library-sync).

The source objective of the tenant meeting library. All content fields
are shared (``both`` — managers curate the library in Odoo or in Evie,
last-write-wins); enums transport the stable keys. Membership of a
meeting template travels on this side (``template_id``): written
outbound by the sync, reconciled inbound only when an inline create
carries it — guarded against every other local change (composition is a
copy action, never a link).
"""

from odoo import _, fields, models

# Selection labels must be plain strings (Odoo translates them itself).
OBJECTIVE_TYPE_SELECTION = [
    ('INFORMATION', 'Information'),
    ('COMMITMENT', 'Commitment'),
    ('PERCEPTION', 'Perception'),
    ('RELATIONSHIP', 'Relationship'),
]

PRIORITY_SELECTION = [
    ('LOW', 'Low'),
    ('MEDIUM', 'Medium'),
    ('HIGH', 'High'),
    ('CRITICAL', 'Critical'),
]


class ObjectiveTemplate(models.Model):
    _name = 'objective.template'
    _description = 'Evie Objective Template'
    _inherit = ['evie.capsule.link', 'evie.meeting.membership.guard',
                'mail.thread']
    _order = 'name'

    #: Locally creatable by managers (library curation from Odoo); the
    #: record starts at sync_state 'pending' (the mixin default).
    _evie_local_create = True

    # --- Shared content (both) ---
    name = fields.Char(string='Label', required=True, tracking=True)
    objective_type = fields.Selection(
        OBJECTIVE_TYPE_SELECTION, string='Objective Type',
        required=True, tracking=True,
        help='Stable Evie key; each type is evaluated differently.')
    intent = fields.Text(string='Intent', required=True)
    success_criterion = fields.Text(string='Success Criterion', required=True)
    guiding_questions = fields.Text(
        string='Guiding Questions',
        help='Example questions, one per line.')
    dimensions = fields.Text(
        string='Dimensions',
        help='Canonical tags (pain, budget, authority, timing, ...), '
             'one per line.')
    default_priority = fields.Selection(
        PRIORITY_SELECTION, string='Default Priority', default='MEDIUM')

    # --- Membership (member side; guarded — see the module guard) ---
    template_id = fields.Many2one(
        'meeting.template', string='Meeting Template',
        index=True, ondelete='set null', readonly=True,
        help='The template this objective is a member of. Membership '
             'changes are copy actions in Evie, never direct links.')

    active = fields.Boolean(default=True)

    def write(self, vals):
        self._check_member_link_write(vals, 'template_id', _('meeting template'))
        return super().write(vals)

    def action_remove_from_template(self):
        """Remove this member from its template via the capsule-actions
        channel (removal is deletion — the copy never returns to
        standalone). The mirror archives via the delete policy on the
        next sync."""
        self.ensure_one()
        import uuid
        if not self.capsule_id:
            from odoo.exceptions import UserError
            raise UserError(_(
                'This objective is not linked to Evie yet; try again after '
                'the next synchronisation.'))
        if not self.template_id:
            from odoo.exceptions import UserError
            raise UserError(_(
                'This objective is not a member of a template.'))
        user = self.env.user
        ok, data = self.env['evie.webhook'].post_for_json('/action-execute', {
            'event_id': str(uuid.uuid4()),
            'action_type': 'REMOVE_TEMPLATE_MEMBER_ACTION',
            'capsule_id': int(self.capsule_id),
            'user': {'name': user.name, 'email': user.email, 'id': user.id},
        })
        if not ok:
            from odoo.exceptions import UserError
            raise UserError(_('Could not remove the objective: %s') % data)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Removed'),
                'message': data.get('message') or _(
                    'The objective is being removed from its template.'),
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
