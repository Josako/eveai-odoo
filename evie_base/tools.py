"""Shared server helpers for the reusable Evie components.

Record-bound Evie components (actions, documents, ...) only receive a
``res_model`` / ``res_id`` pair from the client; these helpers resolve the
record's capsule with the user's access rights checked, and open Evie
entities through the view-token endpoint.
"""

from odoo import _
from odoo.exceptions import UserError

from odoo.addons.evie_base.consts import EVIE_OPEN_KINDS

DEFAULT_CAPSULE_ID_FIELD = 'x_evie_capsule_id'


def evie_record_capsule_id(env, res_model, res_id, capsule_id_field=None):
    """The Evie capsule id of a record the current user may read.

    Archived records (e.g. done activities) resolve too. Returns ``False``
    when the record is not linked to Evie (yet).
    """
    capsule_id_field = capsule_id_field or DEFAULT_CAPSULE_ID_FIELD
    if res_model not in env or not res_id:
        raise UserError(_("Unknown record."))
    record = env[res_model].with_context(active_test=False).browse(int(res_id)).exists()
    if not record:
        raise UserError(_("The record no longer exists."))
    record.check_access('read')
    if capsule_id_field not in record._fields:
        raise UserError(_("This record cannot be linked to Evie."))
    try:
        return int(record[capsule_id_field] or 0) or False
    except (TypeError, ValueError):
        raise UserError(_("This record has an invalid Evie link.")) from None


def evie_open_action(env, kind, reference):
    """URL action opening an Evie entity of a registered kind in a new tab.

    Exchanges the integration API key for a short-lived view token; raises
    ``UserError`` with the endpoint's message on failure.
    """
    request_key = EVIE_OPEN_KINDS.get(kind)
    if not request_key:
        raise UserError(_("Unknown Evie reference type '%s'.") % kind)
    if not reference:
        raise UserError(_("No Evie %s is linked to this record yet.") % kind)
    user = env.user
    ok, data = env['evie.webhook'].post_for_json('/view-token', {
        'kind': kind,
        request_key: int(reference),
        'user': {'name': user.name, 'email': user.email, 'id': user.id},
    })
    if not ok:
        raise UserError(_("Could not open the Evie %s (%s).") % (kind, data))
    return {
        'type': 'ir.actions.act_url',
        'url': data['view_url'],
        'target': 'new',
    }
