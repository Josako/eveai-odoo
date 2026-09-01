"""Evie health/diagnostic surface.

Exposes a machine-readable status that the Evie platform queries via the
Odoo API (JSON-2) to verify a tenant's Odoo side: which ``evie_*`` modules
are installed at which version, and whether the fields/models the integration
requires actually exist. This doubles as the deployment-tier detector:
no ``evie_base`` installed → the tenant is not on Tier 1.

NOTE: EXPECTED_FIELDS below is kept in evie_base but describes the contract
of the vertical modules — bump it together with the vertical's fields.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

#: Fields the integration expects per model, per providing module.
#: ``evie_crm`` keeps its own contract; evie_base reports what is installed.
EXPECTED_MODELS = {
    'evie_crm': ['evie.phase_stage_map', 'evie.activity_type_map',
                 'evie.language_map'],
}
EXPECTED_FIELDS = {
    'evie_crm': {
        'crm.lead': [
            'x_evie_capsule_id',
            'x_evie_phase',
            'x_evie_last_synced',
            # Lead context (evie_crm 19.0.1.1.0, extend-odoo-lead-sync-1)
            'x_evie_source',
            'x_evie_linkedin_url',
            'x_evie_qualification_score',
            'x_evie_report_doc_version_id',
            'x_evie_rationale_doc_version_id',
            # Action lifecycle (evie_crm 19.0.1.4.0, odoo-capsule-actions)
            'x_evie_action_status',
            'x_evie_action_message',
            # Mirrored language (evie_crm 19.0.1.13.0, crm-sync-polish)
            'x_evie_language',
            'x_evie_mapped_language_ids',
        ],
        # Activities (evie_crm 19.0.1.6.0, add-crm-activity-sync)
        'mail.activity': [
            'x_evie_capsule_id',
            'x_evie_activity_type',
            # Outcome sync (evie_crm 19.0.1.7.0, add-activity-sequences)
            'x_evie_outcome',
            # Last-synced anchor (evie_crm 19.0.1.10.0, odoo-evie-form-branding)
            'x_evie_last_synced',
        ],
    },
}


class EvieHealth(models.AbstractModel):
    """Health surface, callable via the API as ``evie.health.get_status``."""

    _name = 'evie.health'
    _description = 'Evie Integration Health'

    @api.model
    def get_status(self, integration_service_id=None):
        """Return module versions and contract presence.

        ``integration_service_id`` is the integration identity handshake
        (integration-run-attention-audit): Evie passes its integration
        service id with the health check; the module persists it as
        ``evie.integration_service_id`` so action executions can carry it
        as audit metadata. The response always includes ``database_uuid``
        so Evie can key the identity to this exact database (a restored or
        duplicated database re-handshakes on the next check).

        Returns a dict::

            {
                'modules': {'evie_base': '19.0.1.0.0', ...},   # installed only
                'missing_modules': ['evie_crm', ...],
                'missing_models': ['evie.phase_stage_map', ...],
                'missing_fields': {'crm.lead': ['x_evie_phase', ...]},
                'database_uuid': '...',
                'ok': bool,
            }
        """
        if integration_service_id:
            self._store_integration_service_id(integration_service_id)
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
            'database_uuid': self.env['ir.config_parameter'].sudo()
                .get_param('database.uuid'),
            'ok': ok,
        }
        _logger.info("Evie health status: %s", status)
        return status

    @api.model
    def _store_integration_service_id(self, integration_service_id):
        """Persist the Evie integration service id (idempotent)."""
        param = self.env['ir.config_parameter'].sudo()
        key = 'evie.integration_service_id'
        value = str(int(integration_service_id))
        if param.get_param(key) != value:
            param.set_param(key, value)
            _logger.info("Evie integration service id provisioned: %s", value)
