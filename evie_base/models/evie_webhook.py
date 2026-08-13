"""Shared webhook helper for all evie_* modules.

Centralises Odoo → Evie webhook POSTs: reads the connection settings
(``evie.webhook_url`` / ``evie.api_key`` config parameters), posts JSON with
an ``X-API-Key`` header and never raises into business flows — failures are
logged and reported via the return value so callers can decide (e.g. schedule
an activity).
"""

import json
import logging
import uuid

import requests

from odoo import api, models

_logger = logging.getLogger(__name__)

#: Keep webhook latency out of user transactions.
WEBHOOK_TIMEOUT_SECONDS = 10


class EvieWebhook(models.AbstractModel):
    _name = 'evie.webhook'
    _description = 'Evie Webhook Client'

    @api.model
    def _connection(self):
        params = self.env['ir.config_parameter'].sudo()
        url = (params.get_param('evie.webhook_url') or '').rstrip('/')
        api_key = params.get_param('evie.api_key') or ''
        return url, api_key

    @api.model
    def is_configured(self):
        """True when both the webhook URL and API key are set."""
        url, api_key = self._connection()
        return bool(url and api_key)

    @api.model
    def post(self, path, payload):
        """POST a JSON payload to an Evie webhook endpoint.

        Args:
            path: endpoint path relative to the configured base URL
                  (e.g. ``'/stage-change'``)
            payload: dict; an ``event_id`` (uuid4) is added when absent

        Returns:
            tuple (ok: bool, detail: str). Never raises for transport or
            HTTP errors — those are logged and returned as ``(False, ...)``.
        """
        url, api_key = self._connection()
        if not url or not api_key:
            _logger.warning("Evie webhook not configured (evie.webhook_url / evie.api_key); "
                            "skipping POST %s", path)
            return False, 'not_configured'

        payload = dict(payload)
        payload.setdefault('event_id', str(uuid.uuid4()))

        try:
            response = requests.post(
                f"{url}/{path.lstrip('/')}",
                data=json.dumps(payload),
                headers={
                    'Content-Type': 'application/json',
                    'X-API-Key': api_key,
                },
                timeout=WEBHOOK_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            _logger.exception("Evie webhook POST %s failed: %s", path, exc)
            return False, f'transport_error: {exc}'

        if response.status_code >= 400:
            _logger.warning("Evie webhook POST %s -> HTTP %s: %s",
                            path, response.status_code, response.text[:500])
            return False, f'http_{response.status_code}'

        _logger.debug("Evie webhook POST %s succeeded (event %s)", path, payload['event_id'])
        return True, payload['event_id']
