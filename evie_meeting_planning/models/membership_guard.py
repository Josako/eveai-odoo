"""Membership-link guard shared by the meeting mirror models
(add-odoo-meeting-library-sync, design decision 2).

Membership travels on the member side (``template_id`` / ``plan_id``):
the sync writes the link outbound, and an inline *create* carries it
inbound. Everything else is forbidden — linking an existing objective
into a template or plan, re-pointing a member, or clearing the link —
because the library's structural mutations are copy actions in Evie,
never link edits. This abstract model provides the single guard those
models call from their ``write``.
"""

from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.evie_base.models.evie_capsule_link import (
    EVIE_SYNC_CONTEXT_KEY,
)


class EvieMeetingMembershipGuard(models.AbstractModel):
    _name = 'evie.meeting.membership.guard'
    _description = 'Evie meeting membership-link guard'

    @api.model
    def _check_member_link_write(self, vals, link_field, parent_description):
        """Refuse non-sync writes that change a membership link.

        Allowed: sync writes (echo-guard context) and creates (the link is
        set at creation, e.g. an inline create on the parent's list — a
        genuine new objective, never a link of an existing one).
        """
        if link_field not in vals:
            return
        if self.env.context.get(EVIE_SYNC_CONTEXT_KEY):
            return
        raise UserError(_(
            "Objectives cannot be linked to or unlinked from a %(parent)s "
            "directly. Pulling objectives in is a copy action — use 'Pull in "
            "objectives (copy)' on the %(parent)s; removing one uses its own "
            "remove affordance."
        ) % {'parent': parent_description})
