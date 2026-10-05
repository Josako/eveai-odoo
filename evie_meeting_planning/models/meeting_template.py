"""Mirror model for MEETING_TEMPLATE capsules
(add-odoo-meeting-library-sync).

A named grouping of source objectives — the unit in which sales and
marketing meeting guidelines are curated. Content is shared (``both``);
membership is the inverse of the member side (``objective_ids`` is
never written by the sync and never edited directly: pulling objectives
in runs via the compose wizard — a copy action — and removing a member
deletes the copy via its own remove action).
"""

from odoo import _, fields, models

from .objective_template import OBJECTIVE_TYPE_SELECTION  # noqa: F401 (re-export for views)


class MeetingTemplate(models.Model):
    _name = 'meeting.template'
    _description = 'Evie Meeting Template'
    _inherit = ['evie.capsule.link', 'mail.thread']
    _order = 'name'

    #: Locally creatable by managers (library curation from Odoo); the
    #: record starts at sync_state 'pending' (the mixin default).
    _evie_local_create = True

    # --- Shared content (both) ---
    name = fields.Char(string='Name', required=True, tracking=True)
    description = fields.Text(string='Description')
    guideline_text = fields.Text(
        string='Guideline Text',
        help='Free-text guidance for the rep (markdown): how to run a '
             'meeting along this template.')
    applicable_meeting_kinds = fields.Text(
        string='Applicable Meeting Kinds',
        help='Meeting kind keys this template is meant for, one per line.')

    # --- Membership: the pure inverse of the member side. Not readonly
    # in the view so managers can inline-create new objectives; linking
    # or removing existing lines is refused by the member-side guard. ---
    objective_ids = fields.One2many(
        'objective.template', 'template_id', string='Objectives')

    active = fields.Boolean(default=True)

    def action_new_objective(self):
        """Create a new objective directly in this template (manager):
        a genuine create carrying the membership at creation — not a
        link of an existing record."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('New objective'),
            'res_model': 'objective.template',
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_template_id': self.id},
        }

    def action_open_compose_wizard(self):
        """Open the compose wizard: pull templates and/or standalone
        objectives into this template as copies (capsule action)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pull in objectives (copy)'),
            'res_model': 'meeting.template.compose.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_template_id': self.id},
        }
