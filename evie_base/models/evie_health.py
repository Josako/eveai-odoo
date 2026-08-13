"""Evie health/diagnostic surface.

Exposes a machine-readable status that the Evie platform queries via the
Odoo API (JSON-2) to verify a tenant's Odoo side: which ``evie_*`` modules
are installed at which version, and whether the fields/models the integration
requires actually exist. This doubles as the deployment-tier detector:
no ``evie_base`` installed → the tenant is not on Tier 1.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

#: Fields the integration expects per model, per providing module.
#: ``evie_crm`` keeps its own contract; evie_base reports what is installed.
EXPECTED_MODELS = {
    'evie_crm': ['evie.phase_stage_map'],
}
EXPECTED_FIELDS = {
    'evie_crm': {
        'crm.lead': ['x_evie_capsule_id', 'x_evie_phase', 'x_evie_last_synced'],
    },
}


class EvieHealth(models.AbstractModel):
    """Health surface, callable via the API as ``evie.health.get_status``."""

    _name = 'evie.health'
    _description = 'Evie Integration Health'

    @api.model
    def get_status(self):
        """Return module versions and contract presence.

        Returns a dict::

            {
                'modules': {'evie_base': '19.0.1.0.0', ...},   # installed only
                'missing_modules': ['evie_crm', ...],
                'missing_models': ['evie.phase_stage_map', ...],
                'missing_fields': {'crm.lead': ['x_evie_phase', ...]},
                'ok': bool,
            }
        """
        module_names = ['evie_base'] + list(EXPECTED_MODELS)
        modules = self.env['ir.module.module'].sudo().search([
            ('name', 'in', module_names),
            ('state', '=', 'installed'),
        ])
        installed = {m.name: m.latest_version for m in modules}

        missing_modules = [name for name in EXPECTED_MODELS if name not in installed]

        missing_models = []
        missing_fields = {}
        for module_name in EXPECTED_MODELS:
            if module_name not in installed:
                continue
            for model_name in EXPECTED_MODELS.get(module_name, []):
                if model_name not in self.env:
                    missing_models.append(model_name)
            for model_name, field_names in EXPECTED_FIELDS.get(module_name, {}).items():
                if model_name not in self.env:
                    continue
                model_fields = self.env[model_name]._fields
                absent = [f for f in field_names if f not in model_fields]
                if absent:
                    missing_fields.setdefault(model_name, []).extend(absent)

        ok = not missing_modules and not missing_models and not missing_fields
        status = {
            'modules': installed,
            'missing_modules': missing_modules,
            'missing_models': missing_models,
            'missing_fields': missing_fields,
            'ok': ok,
        }
        _logger.info("Evie health status: %s", status)
        return status
