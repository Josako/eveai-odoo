"""Read-only mirror model for CAPTURE_FORM capsules (odoo-marketing-adapter).

Form definitions are Evie-master (``out`` only): Odoo shows a readable
overview plus the deeplink to Evie, where forms are edited. No chatter —
every field is outbound-only, so there are no inbound warnings to post.
"""

from odoo import fields, models


class MarketingCaptureForm(models.Model):
    _name = 'marketing.capture.form'
    _description = 'Evie Capture Form'
    _inherit = ['evie.capsule.link']
    _order = 'name'

    name = fields.Char(string='Name', readonly=True)
    status = fields.Selection(
        [('draft', 'Draft'), ('active', 'Active'), ('archived', 'Archived')],
        string='Status', readonly=True)
    definition = fields.Text(
        string='Form Definition', readonly=True,
        help='Form definition as JSON (edited in Evie).')
    consent_text = fields.Text(string='Consent Text', readonly=True)

    channel_ids = fields.One2many(
        'marketing.initiative.channel', 'capture_form_id',
        string='Used by Channels', readonly=True)

    active = fields.Boolean(default=True)
