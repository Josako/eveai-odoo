"""Tenant-extensible marketing type keys (odoo-marketing-mirror-create, D3b).

Evie anchors on stable dynamic-list keys (MARKETING_INITIATIVE_TYPE /
MARKETING_CHANNEL_TYPE, owned by the Evie platform). This map model feeds
the ``type`` / ``channel_type`` dropdowns on the mirror models: one row
per Evie key, seeded with the platform defaults at install (``noupdate``:
tenant edits and additions survive module upgrades). The Evie key is a
plain Char — the dynamic list can gain keys by config alone, without a
module upgrade (the ``evie.activity_type_map`` precedent).

The stored mirror value is always the stable key, never the label; the
label is presentation only and translatable. Inbound pre-validation
against the Evie dynamic list stays the backstop for keys this database
does not know yet.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class EvieMarketingTypeMap(models.Model):
    _name = 'evie.marketing.type.map'
    _description = 'Evie Marketing Type Mapping'
    _order = 'kind, sequence, id'

    sequence = fields.Integer(default=10)
    kind = fields.Selection(
        selection=[('initiative', 'Initiative Type'),
                   ('channel', 'Channel Type')],
        string='Kind', required=True, index=True)
    evie_key = fields.Char(
        string='Evie Key', required=True, index=True,
        help="Stable Evie dynamic-list key (Evie is master; the key matches "
             "MARKETING_INITIATIVE_TYPE or MARKETING_CHANNEL_TYPE on the "
             "Evie side).")
    label = fields.Char(
        string='Label', required=True, translate=True,
        help="Display label in the dropdowns. Presentation only — the "
             "stored value is always the stable key.")
    active = fields.Boolean(default=True)

    display_name = fields.Char(compute='_compute_display_name')

    @api.constrains('kind', 'evie_key')
    def _check_kind_key_unique(self):
        """Duplicate guard with a readable error (deliberately a Python
        check, not a SQL constraint: an administrator adding a key that
        already exists deserves an actionable message, not a raw unique
        violation)."""
        for record in self:
            duplicate = self.search_count([
                ('kind', '=', record.kind),
                ('evie_key', '=', record.evie_key),
                ('id', '!=', record.id),
            ])
            if duplicate:
                raise ValidationError(_(
                    "The key '%(key)s' already exists for kind "
                    "'%(kind)s'.",
                    key=record.evie_key, kind=record.kind))

    @api.depends('evie_key', 'label')
    def _compute_display_name(self):
        for record in self:
            if record.evie_key and record.label and record.evie_key != record.label:
                record.display_name = f"{record.evie_key} → {record.label}"
            else:
                record.display_name = record.evie_key or record.label or ''

    # ------------------------------------------------------------------
    # Selection feeds (the mirror models' dropdowns)
    # ------------------------------------------------------------------

    @api.model
    def selection_for_kind(self, kind):
        """The (key, label) selection list for one kind, in map order."""
        return [
            (record.evie_key, record.label or record.evie_key)
            for record in self.search([('kind', '=', kind)])
        ]
