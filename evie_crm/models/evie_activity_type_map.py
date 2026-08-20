"""Tenant-specific Evie activity type ↔ Odoo activity type mapping.

Evie anchors on stable activity-type keys (the CRM_ACTIVITY_TYPE dynamic
list, owned by the Evie platform); Odoo ``mail.activity.type`` records in
this database are unstable (tenants rename/replace them freely). This model
translates between the two on stable IDs — never on display names. One entry
per Evie key, seeded with defaults at install (noupdate: tenant edits survive
module upgrades).

Unlike the phase mapping, the Evie key is a plain Char: the dynamic list can
gain keys by config alone, without a module upgrade.
"""

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class EvieActivityTypeMap(models.Model):
    _name = 'evie.activity_type_map'
    _description = 'Evie Activity Type Mapping'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    evie_activity_type = fields.Char(
        string='Evie Activity Type',
        required=True,
        index=True,
        help="Stable Evie activity-type key (Evie is master; the key matches "
             "the CRM_ACTIVITY_TYPE dynamic list on the Evie side).",
    )
    odoo_activity_type_id = fields.Many2one(
        'mail.activity.type',
        string='Odoo Activity Type',
        required=True,
        ondelete='restrict',
        help="Odoo activity type used as the presentation for this Evie key.",
    )
    active = fields.Boolean(default=True)

    _key_unique = models.Constraint(
        'unique(evie_activity_type)',
        'Each Evie activity type can only have one mapping entry.',
    )

    display_name = fields.Char(compute='_compute_display_name')

    @api.depends('evie_activity_type', 'odoo_activity_type_id')
    def _compute_display_name(self):
        for record in self:
            record.display_name = (
                f"{record.evie_activity_type or ''} → "
                f"{record.odoo_activity_type_id.name or ''}"
            )

    # ------------------------------------------------------------------
    # Lookup helpers (called by Evie via the JSON-2 API)
    # ------------------------------------------------------------------

    @api.model
    def odoo_type_for_key(self, key):
        """Return the Odoo mail.activity.type id for an Evie key.

        Falls back to the generic To-Do type for unmapped keys — the
        activity always syncs, with ``x_evie_activity_type`` preserving the
        original key.
        """
        if not key:
            return None
        entry = self.search([('evie_activity_type', '=', key)], limit=1)
        if entry:
            return entry.odoo_activity_type_id.id
        return self.env.ref('mail.mail_activity_data_todo').id

    @api.model
    def key_for_odoo_type(self, odoo_type_id):
        """Return the Evie key for an Odoo mail.activity.type id, or None."""
        if not odoo_type_id:
            return None
        entry = self.search([
            ('odoo_activity_type_id', '=', odoo_type_id),
        ], limit=1)
        return entry.evie_activity_type if entry else None
