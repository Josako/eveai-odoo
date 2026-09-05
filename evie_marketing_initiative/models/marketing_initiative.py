"""Mirror model for MARKETING_INITIATIVE capsules (odoo-marketing-adapter).

Editability follows the ownership matrix: the initiative definition is
shared (``both`` — Odoo-editable with write-back), planned budget is
Evie-master (``out``), actual costs are Odoo-master (``in`` — the
``marketing.initiative.cost`` lines below). Derived metrics are computed
locally from constellation facts and never synced. The owner lives on
``user_id``, kept in sync with the capsule's CRM_ASSIGNED_TO_USER
relation via the assignee channel (design D9).

The cost lines are plain Odoo-owned detail records — they never cross
the boundary as capsules; only their computed total (``actual_cost``)
syncs inbound.
"""

from odoo import api, fields, models

from odoo.addons.evie_base.consts import MARKETING_INITIATIVE_TYPE_SELECTION


class MarketingInitiative(models.Model):
    _name = 'marketing.initiative'
    _description = 'Evie Marketing Initiative'
    _inherit = ['evie.capsule.link', 'mail.thread']
    _order = 'date_start desc, name'

    # --- Shared definition (both: Odoo-editable with write-back) ---
    name = fields.Char(string='Name', required=True, tracking=True)
    code = fields.Char(string='Code')
    type = fields.Selection(
        selection=MARKETING_INITIATIVE_TYPE_SELECTION,
        string='Type',
        help='Stable MARKETING_INITIATIVE_TYPE key (labels live in Evie).')
    date_start = fields.Date(string='Start Date')
    date_end = fields.Date(string='End Date')
    location = fields.Char(string='Location')
    country_id = fields.Many2one('res.country', string='Country')
    state = fields.Selection(
        [('draft', 'Draft'), ('planned', 'Planned'), ('active', 'Active'),
         ('completed', 'Completed'), ('archived', 'Archived')],
        string='State', default='draft', tracking=True)
    description = fields.Text(string='Description')
    user_id = fields.Many2one(
        'res.users', string='Owner', tracking=True,
        help='Synced with the capsule\'s CRM_ASSIGNED_TO_USER relation.')

    # --- Evie-master fields (out: read-only in Odoo) ---
    budget = fields.Monetary(
        string='Budget', currency_field='currency_id', readonly=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency', readonly=True)
    attribution_days = fields.Integer(string='Attribution Days', readonly=True)

    # --- UTM strategy (both: editable in Odoo with write-back; the
    # materialised native records below re-derive from these strings) ---
    utm_campaign = fields.Char(string='UTM Campaign')
    utm_medium = fields.Char(string='UTM Medium')
    utm_term = fields.Char(string='UTM Term')
    utm_content = fields.Char(string='UTM Content')

    # --- Materialised native UTM records (out, adopt-or-create) ---
    campaign_id = fields.Many2one('utm.campaign', string='Campaign', readonly=True)
    medium_id = fields.Many2one('utm.medium', string='Medium', readonly=True)

    # --- Odoo-master costs (in: the total syncs to Evie) ---
    cost_ids = fields.One2many(
        'marketing.initiative.cost', 'initiative_id', string='Cost Lines')
    actual_cost = fields.Monetary(
        string='Actual Cost', currency_field='currency_id',
        compute='_compute_actual_cost', store=True, readonly=True)

    # --- Links (written by the sync, never edited locally) ---
    channel_ids = fields.One2many(
        'marketing.initiative.channel', 'initiative_id',
        string='Channels', readonly=True)
    capture_ids = fields.One2many(
        'marketing.capture', 'initiative_id', string='Captures', readonly=True)
    lead_ids = fields.One2many(
        'crm.lead', 'initiative_id', string='Leads', readonly=True)

    # --- Derived metrics (computed from facts, never synced) ---
    capture_count = fields.Integer(
        string='Capture Count', compute='_compute_derived_metrics')
    lead_count = fields.Integer(
        string='Lead Count', compute='_compute_derived_metrics')
    cost_per_capture = fields.Monetary(
        string='Cost per Capture', currency_field='currency_id',
        compute='_compute_derived_metrics')
    roi = fields.Float(
        string='ROI %', compute='_compute_derived_metrics')

    active = fields.Boolean(default=True)

    @api.depends('cost_ids.amount')
    def _compute_actual_cost(self):
        for initiative in self:
            initiative.actual_cost = sum(initiative.cost_ids.mapped('amount'))

    @api.depends('capture_ids', 'lead_ids', 'actual_cost',
                 'lead_ids.expected_revenue')
    def _compute_derived_metrics(self):
        for initiative in self:
            captures = len(initiative.capture_ids)
            initiative.capture_count = captures
            initiative.lead_count = len(initiative.lead_ids)
            initiative.cost_per_capture = (
                initiative.actual_cost / captures if captures else 0.0)
            expected = sum(initiative.lead_ids.mapped('expected_revenue'))
            initiative.roi = (
                (expected - initiative.actual_cost) / initiative.actual_cost * 100
                if initiative.actual_cost else 0.0)


class MarketingInitiativeCost(models.Model):
    """Odoo-owned cost line of an initiative (never a capsule).

    Optionally linked to a vendor bill in a later iteration — v1 keeps the
    model dependency-free (no ``account`` dependency).
    """
    _name = 'marketing.initiative.cost'
    _description = 'Marketing Initiative Cost'
    _order = 'date desc, id desc'

    initiative_id = fields.Many2one(
        'marketing.initiative', string='Initiative',
        required=True, ondelete='cascade', index=True)
    name = fields.Char(string='Description', required=True)
    date = fields.Date(string='Date', default=fields.Date.context_today)
    amount = fields.Monetary(string='Amount', currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        related='initiative_id.currency_id', store=True, readonly=True)
