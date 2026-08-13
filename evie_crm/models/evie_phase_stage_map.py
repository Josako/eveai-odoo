"""Tenant-specific Evie phase ↔ Odoo type/stage mapping.

Evie anchors on stable funnel phases; stages in this database are unstable
(tenants rename/reorder them freely). This model translates between the two
on stable stage IDs — never on display names. One entry per phase, seeded
with defaults at install (noupdate: tenant edits survive module upgrades).
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.evie_base.consts import EVIE_PHASE_SELECTION

_logger = logging.getLogger(__name__)


class EviePhaseStageMap(models.Model):
    _name = 'evie.phase_stage_map'
    _description = 'Evie Phase ↔ Stage Mapping'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    phase = fields.Selection(
        selection=EVIE_PHASE_SELECTION,
        string='Evie Phase',
        required=True,
        index=True,
        help="Stable Evie funnel phase (Evie is master; keys never change).",
    )
    odoo_type = fields.Selection(
        selection=[('lead', 'Lead'), ('opportunity', 'Opportunity')],
        string='Odoo Type',
        required=True,
        default='lead',
    )
    odoo_stage_id = fields.Many2one(
        'crm.stage',
        string='Odoo Stage',
        ondelete='restrict',
        help="Stage for this phase. Required and only meaningful for opportunities.",
    )
    is_default_for_phase = fields.Boolean(
        string='Default',
        default=True,
        help="When several stages map to the same phase, the default is used "
             "for the forward (Evie → Odoo) direction.",
    )
    active = fields.Boolean(default=True)

    _phase_unique = models.Constraint(
        'unique(phase)',
        'Each Evie phase can only have one mapping entry.',
    )

    @api.constrains('odoo_type', 'odoo_stage_id')
    def _check_stage_consistency(self):
        for record in self:
            if record.odoo_type == 'opportunity' and not record.odoo_stage_id:
                raise ValidationError(_(
                    "An opportunity mapping requires an Odoo stage (phase '%s').",
                    record.phase,
                ))
            if record.odoo_type == 'lead' and record.odoo_stage_id:
                raise ValidationError(_(
                    "A lead mapping cannot have a stage (phase '%s'); "
                    "leads do not live in the pipeline Kanban.",
                    record.phase,
                ))

    @api.constrains('phase', 'is_default_for_phase')
    def _check_single_default(self):
        for record in self.filtered('is_default_for_phase'):
            others = self.search([
                ('phase', '=', record.phase),
                ('is_default_for_phase', '=', True),
                ('id', '!=', record.id),
            ])
            if others:
                raise ValidationError(_(
                    "Only one mapping entry can be the default for phase '%s'.",
                    record.phase,
                ))

    display_name = fields.Char(compute='_compute_display_name')

    @api.depends('phase', 'odoo_type', 'odoo_stage_id')
    def _compute_display_name(self):
        type_labels = dict(self._fields['odoo_type'].selection)
        for record in self:
            label = f"{record.phase} → {type_labels.get(record.odoo_type, '')}"
            if record.odoo_stage_id:
                label += f" / {record.odoo_stage_id.name}"
            record.display_name = label


    # ------------------------------------------------------------------
    # Lookup helpers (used by crm.lead automation paths)
    # ------------------------------------------------------------------

    @api.model
    def phase_for_stage(self, stage_id):
        """Return the Evie phase for a crm.stage id, or None when unmapped."""
        if not stage_id:
            return None
        entry = self.search([('odoo_stage_id', '=', stage_id)], limit=1)
        return entry.phase if entry else None

    @api.model
    def target_for_phase(self, phase):
        """Return {'odoo_type', 'odoo_stage_id'} for a phase, or None when unmapped."""
        if not phase:
            return None
        entry = self.search([
            ('phase', '=', phase),
            ('is_default_for_phase', '=', True),
        ], limit=1)
        if not entry:
            return None
        return {
            'odoo_type': entry.odoo_type,
            'odoo_stage_id': entry.odoo_stage_id.id or None,
        }

    # ------------------------------------------------------------------
    # Mapping-change notification (called by the automation rule)
    # ------------------------------------------------------------------

    @api.model
    def evie_notify_mapping_changed(self):
        """Ping Evie so it invalidates its mapping cache."""
        ok, detail = self.env['evie.webhook'].post('/mapping-changed', {
            'event': 'mapping_changed',
        })
        if not ok:
            _logger.warning("Evie mapping-changed notification failed: %s", detail)
        return ok
