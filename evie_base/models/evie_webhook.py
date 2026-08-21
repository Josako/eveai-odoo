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

#: The connection test waits for Evie's live reverse check (Evie → Odoo),
#: so it needs a longer budget than fire-and-forget webhooks.
CONNECTION_TEST_TIMEOUT_SECONDS = 30


def _error_detail(response):
    """Best-effort error detail for a failed call: Evie's message when the
    body carries one (meaningful for the user), else the HTTP status."""
    try:
        body = response.json()
        if isinstance(body, dict) and body.get('message'):
            return body['message']
    except ValueError:
        pass
    return f'http_{response.status_code}'


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

    @api.model
    def test_connection(self, url=None, api_key=None):
        """Full-duplex connection test: ping Evie and report both directions.

        Posts to the ``/ping`` endpoint with full error capture (unlike the
        fire-and-forget :meth:`post`). Never raises into business flows and
        never logs or returns the API key.

        Args:
            url: override for the configured webhook URL (e.g. the unsaved
                value in the settings form); defaults to the configured one
            api_key: override for the configured API key; defaults to the
                configured one

        Returns:
            tuple (ok: bool, detail: str, data: dict). ``detail`` is a short
            machine-readable key on failure ('timeout', 'tls_error: ...',
            'unreachable: ...', 'authentication_failed',
            'no_active_integration', 'http_<status>'), 'ok' on success with
            ``data`` holding the ping payload (Evie's view of the link plus
            the reverse check result).
        """
        configured_url, configured_key = self._connection()
        url = (url if url is not None else configured_url or '').rstrip('/')
        api_key = api_key if api_key is not None else configured_key
        if not url or not api_key:
            return False, 'not_configured', {}

        try:
            response = requests.post(
                f"{url}/ping",
                data='{}',
                headers={
                    'Content-Type': 'application/json',
                    'X-API-Key': api_key,
                },
                timeout=CONNECTION_TEST_TIMEOUT_SECONDS,
            )
        except requests.exceptions.SSLError as exc:
            _logger.warning("Evie connection test: TLS error: %s", exc)
            return False, f'tls_error: {exc}', {}
        except requests.exceptions.Timeout:
            return False, 'timeout', {}
        except requests.exceptions.ConnectionError as exc:
            _logger.warning("Evie connection test: cannot connect: %s", exc)
            return False, f'unreachable: {exc}', {}
        except requests.RequestException as exc:
            _logger.exception("Evie connection test failed: %s", exc)
            return False, f'transport_error: {exc}', {}

        if response.status_code == 401:
            return False, 'authentication_failed', {}
        if response.status_code == 409:
            return False, 'no_active_integration', {}
        if response.status_code >= 400:
            _logger.warning("Evie connection test -> HTTP %s: %s",
                            response.status_code, response.text[:500])
            return False, f'http_{response.status_code}', {}

        try:
            return True, 'ok', response.json()
        except ValueError:
            return False, 'invalid_json', {}

    @api.model
    def post_for_json(self, path, payload):
        """POST a JSON payload and parse the JSON response body.

        Unlike :meth:`post` (fire-and-forget events), this variant is for
        request/response calls such as the external document view-token
        exchange.

        Args:
            path: endpoint path relative to the configured base URL
            payload: dict

        Returns:
            tuple (ok: bool, data: dict | detail: str). Never raises for
            transport or HTTP errors.
        """
        url, api_key = self._connection()
        if not url or not api_key:
            _logger.warning("Evie webhook not configured (evie.webhook_url / evie.api_key); "
                            "skipping POST %s", path)
            return False, 'not_configured'

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
            _logger.exception("Evie POST %s failed: %s", path, exc)
            return False, f'transport_error: {exc}'

        if response.status_code >= 400:
            _logger.warning("Evie POST %s -> HTTP %s: %s",
                            path, response.status_code, response.text[:500])
            return False, _error_detail(response)

        try:
            return True, response.json()
        except ValueError:
            _logger.warning("Evie POST %s returned non-JSON body", path)
            return False, 'invalid_json'

    @api.model
    def get_for_json(self, path, params=None):
        """GET a JSON endpoint and parse the JSON response body.

        GET variant of :meth:`post_for_json`, for read-only endpoints such
        as the capsule action discovery.

        Args:
            path: endpoint path relative to the configured base URL
            params: optional query parameters dict

        Returns:
            tuple (ok: bool, data: dict | detail: str). Never raises for
            transport or HTTP errors.
        """
        url, api_key = self._connection()
        if not url or not api_key:
            _logger.warning("Evie webhook not configured (evie.webhook_url / evie.api_key); "
                            "skipping GET %s", path)
            return False, 'not_configured'

        try:
            response = requests.get(
                f"{url}/{path.lstrip('/')}",
                params=params,
                headers={'X-API-Key': api_key},
                timeout=WEBHOOK_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            _logger.exception("Evie GET %s failed: %s", path, exc)
            return False, f'transport_error: {exc}'

        if response.status_code >= 400:
            _logger.warning("Evie GET %s -> HTTP %s: %s",
                            path, response.status_code, response.text[:500])
            return False, _error_detail(response)

        try:
            return True, response.json()
        except ValueError:
            _logger.warning("Evie GET %s returned non-JSON body", path)
            return False, 'invalid_json'
