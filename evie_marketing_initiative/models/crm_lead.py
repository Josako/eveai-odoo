"""crm.lead extension for the marketing projection (odoo-marketing-adapter).

Attribution of a lead to its marketing origin: the initiative, channel
and originating capture (all written by the sync via the
CAPTURE_GENERATED_LEAD relation chain — never edited locally), the
capture's score (a stored related read-through, zero sync plumbing) and
the two UTM parameters Odoo has no native models for. Campaign, source
and medium use the NATIVE crm.lead fields (materialised by the sync via
adopt-or-create), so Odoo's marketing attribution reporting works
unchanged. Deliberately no ``utm.term``/``utm.content`` models.
"""

from odoo import fields, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    initiative_id = fields.Many2one(
        'marketing.initiative', string='Marketing Initiative',
        readonly=True, index=True, ondelete='set null')
    initiative_channel_id = fields.Many2one(
        'marketing.initiative.channel', string='Marketing Channel',
        readonly=True, index=True, ondelete='set null')
    capture_id = fields.Many2one(
        'marketing.capture', string='Origin Capture',
        readonly=True, ondelete='set null')
    capture_score = fields.Integer(
        string='Capture Score', related='capture_id.score',
        store=True, readonly=True)
    utm_term = fields.Char(string='UTM Term', readonly=True)
    utm_content = fields.Char(string='UTM Content', readonly=True)
