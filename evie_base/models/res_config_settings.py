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

    def action_test_evie_connection(self):
        """Test the Evie link in both directions and show the outcome.

        Uses the values currently in the form (saved or not), so an
        administrator can test before saving. The API key is never
        displayed.
        """
        self.ensure_one()
        url = (self.evie_webhook_url or '').strip()
        api_key = (self.evie_api_key or '').strip()

        missing = []
        if not url:
            missing.append('Webhook URL')
        if not api_key:
            missing.append('API Key')
        if missing:
            return self._evie_test_notification(
                'Evie connection not configured',
                f"Fill in {', '.join(missing)} and test again.",
                'warning',
            )

        ok, detail, data = self.env['evie.webhook'].test_connection(
            url=url, api_key=api_key,
        )
        if not ok:
            return self._evie_test_notification(
                'Connection failed',
                self._evie_test_failure_message(detail),
                'danger', sticky=True,
            )

        integration = data.get('integration') or {}
        reverse = data.get('reverse') or {}
        lines = ['Evie accepted the call — the Odoo → Evie direction works.']
        if integration.get('status'):
            lines.append(f"Integration status in Evie: {integration['status']}.")
        if integration.get('last_heartbeat'):
            lines.append(f"Last inbound activity: {integration['last_heartbeat']}.")
        if reverse.get('ok'):
            lines.append(f"Reverse check (Evie → Odoo): {reverse.get('message')}")
            return self._evie_test_notification(
                'Connection OK', '\n'.join(lines), 'success', sticky=True,
            )
        lines.append(
            f"Reverse check (Evie → Odoo) FAILED: {reverse.get('message')}"
        )
        return self._evie_test_notification(
            'Connection partially working', '\n'.join(lines), 'warning',
            sticky=True,
        )

    @api.model
    def _evie_test_failure_message(self, detail):
        """Map a machine-readable test failure detail to a clear message."""
        if detail == 'not_configured':
            return ('The Evie connection is not configured: set the Webhook '
                    'URL and API Key first.')
        if detail == 'timeout':
            return ('Evie did not respond in time — check the Webhook URL '
                    'and that this server can reach Evie.')
        if detail.startswith('tls_error:'):
            return (f"TLS/certificate error connecting to Evie: "
                    f"{detail[len('tls_error: '):]}")
        if detail.startswith('unreachable:'):
            return (f"Evie is unreachable: {detail[len('unreachable: '):]} "
                    f"— check the Webhook URL (DNS, host, port).")
        if detail == 'authentication_failed':
            return ('Evie rejected the API key (HTTP 401) — check the API '
                    'key.')
        if detail == 'no_active_integration':
            return ('Evie reports no active Odoo integration for this '
                    'tenant (HTTP 409) — configure and activate the '
                    'integration in Evie first.')
        if detail.startswith('http_'):
            return (f"Evie returned HTTP {detail[len('http_'):]} — check "
                    f"that the Webhook URL points to the Evie webhook "
                    f"endpoints.")
        return f'Connection test failed: {detail}'

    @api.model
    def _evie_test_notification(self, title, message, notification_type,
                                sticky=False):
        """Build a display_notification client action for the test outcome."""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': notification_type,
                'sticky': sticky,
            },
        }

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
