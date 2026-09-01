"""Tenant-specific Evie language ↔ Odoo res.lang mapping.

Evie anchors on stable ISO 639-1 language codes; this database's res.lang
records are locale-level (nl_NL vs nl_BE — a tenant choice, never a sync
guess). One entry per Evie language, seeded with defaults at install
(noupdate: tenant edits survive module upgrades). Both directions are
unique: one res.lang per Evie code, one Evie code per res.lang — so the
reverse lookup (Odoo → Evie) is always unambiguous. No default fallback:
an unmapped language is skipped by the sync (never cleared), by design
(crm-sync-polish).
"""

import logging

from odoo import fields, models

from odoo.addons.evie_base.consts import EVIE_LANGUAGE_SELECTION

_logger = logging.getLogger(__name__)


class EvieLanguageMap(models.Model):
    _name = 'evie.language_map'
    _description = 'Evie Language ↔ res.lang Mapping'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    evie_language = fields.Selection(
        selection=EVIE_LANGUAGE_SELECTION,
        string='Evie Language',
        required=True,
        index=True,
        help="Stable Evie language code (ISO 639-1; Evie is master).",
    )
    odoo_lang_id = fields.Many2one(
        'res.lang',
        string='Odoo Language',
        required=True,
        ondelete='restrict',
        help="The res.lang this Evie code translates to — e.g. choose "
             "Dutch (BE) or Dutch (NL) for 'nl'.",
    )
    active = fields.Boolean(default=True)

    _evie_language_unique = models.Constraint(
        'unique(evie_language)',
        'Each Evie language can only have one mapping entry.',
    )
    _odoo_lang_unique = models.Constraint(
        'unique(odoo_lang_id)',
        'Each Odoo language can only be mapped to one Evie language — the '
        'reverse (Odoo → Evie) lookup must stay unambiguous.',
    )
