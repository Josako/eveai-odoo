"""Server side of the generic Evie action component (odoo-capsule-actions).

Fetches the configured data capsule actions for a capsule type from the Evie
discovery endpoint (cached with a TTL) and executes them via the generic
action-execute endpoint. Action definitions are never hardcoded in Odoo —
adding an action in the Evie configuration is enough.

The discovery fetch never raises: failures return ``ok: False`` so the OWL
component degrades to an unobtrusive placeholder. Execution failures raise
``UserError`` so the user gets the endpoint's message as a dialog (same
pattern as ``action_evie_open``).
"""

import logging
import time
import uuid

from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.tools import ormcache

_logger = logging.getLogger(__name__)

#: TTL of the discovery cache (seconds). Actions change only with Evie
#: platform deploys, so a stale window in this range is harmless.
ACTION_CACHE_TTL_SECONDS = 1800  # 30 minutes


class EvieActions(models.AbstractModel):
    _name = 'evie.actions'
    _description = 'Evie Data Capsule Actions'

    @api.model
    def get_actions(self, capsule_type):
        """Return the discovered actions for a capsule type.

        Cached server-side with a time-bucket TTL (per worker, per capsule
        type). Never raises.

        Returns:
            dict: ``{'ok': bool, 'actions': [...]}``
        """
        if not capsule_type:
            return {'ok': False, 'actions': []}
        bucket = int(time.time() // ACTION_CACHE_TTL_SECONDS)
        return self._get_actions_cached(capsule_type, bucket)

    @api.model
    @ormcache('capsule_type', 'bucket')
    def _get_actions_cached(self, capsule_type, bucket):
        ok, data = self.env['evie.webhook'].get_for_json(
            '/capsule-actions', params={'capsule_type': capsule_type})
        if not ok:
            _logger.warning(
                "Evie action discovery failed for %s: %s", capsule_type, data)
            return {'ok': False, 'actions': []}
        return {'ok': True, 'actions': data.get('actions', [])}

    @api.model
    def execute_action(self, action_type, capsule_id=None, remote_id=None,
                       specialist_id=None):
        """Execute an action via the generic action-execute endpoint.

        The current Odoo user is sent as audit information only (Evie never
        resolves it to an Evie user), together with the integration service
        id provisioned via the health-check handshake (absent on older
        installs — Evie tolerates that). For interactive actions the user's
        ``lang`` travels along so the popup chat session speaks the user's
        language. Returns the endpoint's result data on success — for
        interactive actions that is ``{'kind': 'chat', 'url', ...}`` (the
        popup chat URL to open); raises ``UserError`` with the endpoint's
        message on failure so the user sees a meaningful dialog.
        """
        user = self.env.user
        payload = {
            'event_id': str(uuid.uuid4()),
            'action_type': action_type,
            'user': {'name': user.name, 'email': user.email, 'lang': user.lang,
                     'id': user.id},
        }
        integration_service_id = self.env['ir.config_parameter'].sudo() \
            .get_param('evie.integration_service_id')
        if integration_service_id:
            payload['integration_service_id'] = int(integration_service_id)
        if capsule_id:
            payload['capsule_id'] = int(capsule_id)
        if remote_id:
            payload['remote_id'] = int(remote_id)
        if specialist_id:
            payload['specialist_id'] = int(specialist_id)

        ok, data = self.env['evie.webhook'].post_for_json('/action-execute', payload)
        if not ok:
            raise UserError(_("Could not execute the Evie action: %s") % data)
        # Interactive actions (interactive-activity-proposal-entry-points):
        # the endpoint resolved-or-created the capsule's proposal session and
        # returned a popup chat URL instead of enqueueing a background run —
        # pass it through for the widget to open.
        if isinstance(data, dict) and data.get('kind') == 'chat' and data.get('url'):
            _logger.info(
                "Evie interactive action %s returned a chat URL (remote id %s)",
                action_type, remote_id)
            return {'kind': 'chat', 'url': data['url'],
                    'expires_in': data.get('expires_in')}
        _logger.info("Evie action %s executed (remote id %s): %s",
                     action_type, remote_id, data)
        return data
