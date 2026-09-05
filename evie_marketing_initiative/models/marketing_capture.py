"""Mirror model for CAPTURE capsules (odoo-marketing-adapter).

Capture facts are Evie-master (``out``, read-only); only the decision
fields are shared (``both``, last-write-wins with both values in the
audit trail on each side). Identity matches on ``external_uuid``
(client-generated at capture time), never on names. The initiative,
channel and generated-lead links are constellation relations resolved
by the sync, never edited locally.
"""

from odoo import fields, models


class MarketingCapture(models.Model):
    _name = 'marketing.capture'
    _description = 'Evie Marketing Capture'
    _inherit = ['evie.capsule.link', 'mail.thread']
    _order = 'captured_at desc, id desc'

    # --- Identity (out; the matching key) ---
    external_uuid = fields.Char(
        string='External UUID', readonly=True, required=True, index=True,
        help='Client-generated UUID recorded at capture time.')

    # --- Capture facts (out, read-only) ---
    name = fields.Char(string='Contact Name', readonly=True)
    email = fields.Char(string='Email', readonly=True)
    phone = fields.Char(string='Phone', readonly=True)
    company_name = fields.Char(string='Company', readonly=True)
    job_title = fields.Char(string='Job Title', readonly=True)
    answers = fields.Text(string='Answers', readonly=True)
    answer_summary = fields.Text(string='Answer Summary', readonly=True)
    score = fields.Integer(string='Score', readonly=True)
    consent_ref = fields.Char(string='Consent Reference', readonly=True)
    captured_at = fields.Datetime(string='Captured At', readonly=True)
    state = fields.Selection(
        [('new', 'New'), ('to_review', 'To Review'),
         ('processed', 'Processed'), ('discarded', 'Discarded')],
        string='State', readonly=True)

    # --- Links (written by the sync, never edited locally) ---
    initiative_id = fields.Many2one(
        'marketing.initiative', string='Initiative',
        readonly=True, index=True, ondelete='set null')
    channel_id = fields.Many2one(
        'marketing.initiative.channel', string='Channel',
        readonly=True, index=True, ondelete='set null')
    lead_id = fields.Many2one(
        'crm.lead', string='Generated Lead', readonly=True, ondelete='set null')

    # --- Decision fields (both: last-write-wins, audited on both sides) ---
    decision_source = fields.Selection(
        [('human', 'Human'), ('agent', 'Agent')],
        string='Decision Source', tracking=True)
    decision_certainty = fields.Integer(string='Decision Certainty')
    decision_rationale = fields.Text(string='Decision Rationale')
    decided_at = fields.Datetime(string='Decided At')

    active = fields.Boolean(default=True)
