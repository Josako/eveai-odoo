"""Compose wizard for meeting templates (add-odoo-meeting-library-sync).

Pulls meeting templates and/or standalone objectives into the current
template as COPIES via the capsule-actions channel
(COMPOSE_MEETING_TEMPLATE_ACTION with runtime arguments) — the only way
to add existing library content to a template, because composition is a
copy action in Evie, never a link. The new members arrive on the mirror
via the ordinary outbound sync.
"""

import uuid

from odoo import _, fields, models
from odoo.exceptions import UserError


class MeetingTemplateComposeWizard(models.TransientModel):
    _name = 'meeting.template.compose.wizard'
    _description = 'Pull objectives into a meeting template (copy)'

    template_id = fields.Many2one(
        'meeting.template', string='Template', required=True, readonly=True)
    source_template_ids = fields.Many2many(
        'meeting.template', 'meeting_template_compose_template_rel',
        'wizard_id', 'template_id', string='Pull in all objectives of',
        domain="[('id', '!=', template_id), ('capsule_id', '!=', False)]")
    source_objective_ids = fields.Many2many(
        'objective.template', 'meeting_template_compose_objective_rel',
        'wizard_id', 'objective_id', string='Pull in these objectives',
        domain="[('template_id', '=', False), ('capsule_id', '!=', False)]")

    def action_compose(self):
        self.ensure_one()
        if not self.template_id.capsule_id:
            raise UserError(_(
                'This template is not linked to Evie yet; try again after '
                'the next synchronisation.'))
        if not self.source_template_ids and not self.source_objective_ids:
            raise UserError(_('Select at least one template or objective.'))
        user = self.env.user
        arguments = {}
        template_capsule_ids = [
            ref for ref in self.source_template_ids.mapped('capsule_id') if ref]
        objective_capsule_ids = [
            ref for ref in self.source_objective_ids.mapped('capsule_id') if ref]
        if template_capsule_ids:
            arguments['template_ids'] = ','.join(template_capsule_ids)
        if objective_capsule_ids:
            arguments['objective_ids'] = ','.join(objective_capsule_ids)
        if not arguments:
            raise UserError(_(
                'The selected records are not linked to Evie yet; try again '
                'after the next synchronisation.'))
        ok, data = self.env['evie.webhook'].post_for_json('/action-execute', {
            'event_id': str(uuid.uuid4()),
            'action_type': 'COMPOSE_MEETING_TEMPLATE_ACTION',
            'capsule_id': int(self.template_id.capsule_id),
            'arguments': arguments,
            'user': {'name': user.name, 'email': user.email, 'id': user.id},
        })
        if not ok:
            raise UserError(_('Could not compose the template: %s') % data)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Composed'),
                'message': data.get('message') or _(
                    'The objectives are being copied in; they appear here '
                    'after the next synchronisation.'),
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
