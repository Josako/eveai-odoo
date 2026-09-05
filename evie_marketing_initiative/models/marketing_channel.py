"""Mirror model for MARKETING_CHANNEL capsules (odoo-marketing-adapter).

The channel definition is shared (``both`` — Odoo-editable with
write-back); ``crm_defaults`` is Odoo-master (``in`` — opaque adapter
values Evie stores and transports verbatim, never interprets). The UTM
source string is materialised onto a native ``utm.source`` record by the
sync (adopt-or-create); ``initiative_id`` and ``capture_form_id`` are
relation links resolved by the sync, never edited locally.
"""

from odoo import fields, models


class MarketingInitiativeChannel(models.Model):
    _name = 'marketing.initiative.channel'
    _description = 'Evie Marketing Channel'
    _inherit = ['evie.capsule.link', 'mail.thread']
    _order = 'initiative_id, name'

    # --- Shared definition (both) ---
    name = fields.Char(string='Name', required=True, tracking=True)
    channel_type = fields.Char(
        string='Channel Type Key', required=True, tracking=True,
        help='Stable MARKETING_CHANNEL_TYPE key (labels live in Evie).')
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

    # --- Links (written by the sync, never edited locally) ---
    initiative_id = fields.Many2one(
        'marketing.initiative', string='Initiative',
        readonly=True, index=True, ondelete='set null')
    capture_form_id = fields.Many2one(
        'marketing.capture.form', string='Capture Form',
        readonly=True, ondelete='set null')
    capture_ids = fields.One2many(
        'marketing.capture', 'channel_id', string='Captures', readonly=True)

    # --- Materialised native UTM record (out, adopt-or-create) ---
    source_id = fields.Many2one('utm.source', string='Source', readonly=True)

    active = fields.Boolean(default=True)
