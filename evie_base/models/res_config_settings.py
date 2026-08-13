"""Evie connection settings.

Stored as ir.config_parameter values so every ``evie_*`` module can reach them:

* ``evie.webhook_url`` — base URL of the Evie webhook endpoints
  (e.g. ``https://evie.example.com/api/v1/integrations/odoo``)
* ``evie.api_key`` — TenantProject API key used to authenticate
  Odoo → Evie webhook calls
"""

from odoo import fields, models


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
