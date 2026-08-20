"""Evie connection settings.

Stored as ir.config_parameter values so every ``evie_*`` module can reach them:

* ``evie.webhook_url`` — base URL of the Evie webhook endpoints
  (e.g. ``https://evie.example.com/api/v1/integrations/odoo``)
* ``evie.api_key`` — TenantProject API key used to authenticate
  Odoo → Evie webhook calls

Also surfaces the installed ``evie_*`` module versions (read-only, computed)
so an admin can verify at a glance which module versions this database runs
— the first thing to check when a tenant reports integration problems.
"""

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    evie_webhook_url = fields.Char(
        string='Evie Webhook URL',
        config_parameter='evie.webhook_url',
        help="Base URL of the Evie webhook endpoints, e.g. "
             "https://evie.example.com/api/v1/integrations/odoo",
    )
    evie_api_key = fields.Char(
        string='Evie API Key',
        config_parameter='evie.api_key',
        help="TenantProject API key used to authenticate Odoo → Evie webhooks.",
    )
    evie_module_versions = fields.Char(
        string='Evie Module Versions',
        compute='_compute_evie_module_versions',
        help="Installed evie_* modules and their versions in this database. "
             "Evie checks a minimum version via the health check; compare "
             "here when the integration reports a version mismatch.",
    )

    @api.depends('evie_webhook_url')
    def _compute_evie_module_versions(self):
        modules = self.env['ir.module.module'].sudo().search([
            ('name', 'like', r'evie\_%'),
            ('state', '=', 'installed'),
        ], order='name')
        summary = ', '.join(
            f"{m.name} {m.latest_version}" for m in modules
        ) or '—'
        for record in self:
            record.evie_module_versions = summary
