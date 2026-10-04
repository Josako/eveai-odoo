"""Mirror model for MARKETING_CHANNEL capsules (odoo-marketing-adapter).

The channel definition is shared (``both`` — Odoo-editable with
write-back); ``crm_defaults`` is Odoo-master (``in`` — opaque adapter
values Evie stores and transports verbatim, never interprets). The UTM
source string is materialised onto a native ``utm.source`` record by the
sync (adopt-or-create). ``initiative_id`` and ``capture_form_id`` are
relation links shared with Evie (``both`` since
odoo-marketing-mirror-create): settable here, reconciled inbound as
constellation relations, and written outbound from the Evie relations —
last-write-wins.
"""

from odoo import api, fields, models


class MarketingInitiativeChannel(models.Model):
    _name = 'marketing.initiative.channel'
    _description = 'Evie Marketing Channel'
    _inherit = ['evie.capsule.link', 'mail.thread']
    _order = 'initiative_id, name'

    #: Locally creatable (odoo-marketing-mirror-create): a user may
    #: assemble a channel in Odoo — including its initiative and capture
    #: form links, which reconcile inbound as constellation relations.
    #: The record starts at sync_state 'pending' (the mixin default).
    _evie_local_create = True

    # --- Shared definition (both) ---
    name = fields.Char(string='Name', required=True, tracking=True)
    channel_type = fields.Selection(
        selection='_selection_channel_type',
        string='Channel Type', required=True, tracking=True,
        help='Stable MARKETING_CHANNEL_TYPE key (labels live in the '
             'tenant-editable Evie marketing type map).')
    channel_type_other = fields.Char(
        string='Other Channel Type',
        help='Free-text specification when the type is Other.')
    utm_source = fields.Char(string='UTM Source')
    auto_promote = fields.Boolean(string='Auto Promote')
    auto_promote_threshold = fields.Integer(string='Auto Promote Threshold')

    # --- Odoo-master (in: opaque adapter values) ---
    crm_defaults = fields.Text(
        string='CRM Defaults',
        help='Adapter-specific defaults for created leads (JSON). Evie '
             'stores and transports them verbatim and never interprets '
             'their meaning.')

    # --- Links (both since odoo-marketing-mirror-create: editable in
    # Odoo; the sync also writes them outbound from the Evie relations,
    # last-write-wins — edits reconcile inbound as constellation
    # relations: INITIATIVE_HAS_CHANNEL reverse, CHANNEL_USES_FORM
    # forward. The form link stays optional: a formless channel is valid.)
    initiative_id = fields.Many2one(
        'marketing.initiative', string='Initiative',
        index=True, ondelete='set null', tracking=True)
    capture_form_id = fields.Many2one(
        'marketing.capture.form', string='Capture Form',
        ondelete='set null', tracking=True)
    capture_ids = fields.One2many(
        'marketing.capture', 'channel_id', string='Captures', readonly=True)

    def action_open_capture_list(self):
        """Open the Evie capture list popup scoped to this channel
        (capture-list-view): the same screen an Evie user sees, with the
        asserted integration user as actor of any action inside."""
        self.ensure_one()
        return self.action_evie_open('capture_list', self.capsule_id)

    # --- Materialised native UTM record (out, adopt-or-create) ---
    source_id = fields.Many2one('utm.source', string='Source', readonly=True)

    active = fields.Boolean(default=True)

    @api.model
    def _selection_channel_type(self):
        """Dropdown fed by the tenant-editable type map (D3b): a tenant-
        added Evie dynamic-list key becomes selectable by adding a map
        row, without a module upgrade. The stored value is the key."""
        return self.env['evie.marketing.type.map'].selection_for_kind(
            'channel')
