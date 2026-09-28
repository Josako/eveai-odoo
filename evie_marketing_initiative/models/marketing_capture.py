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
    # Business card reference (odoo-capture-card-view): the Evie document
    # version id of the scanned card — a plain integer reference, never a
    # synced image binary. Rendered as an open-in-Evie link of kind
    # 'capture_media' (tokenised read-only media page streams the original
    # through Evie; the bytes never cross the boundary).
    business_card = fields.Integer(
        string='Business Card', readonly=True,
        help='Evie document version id of the scanned business card image. '
             'Opens a read-only media view in Evie.')
    captured_at = fields.Datetime(string='Captured At', readonly=True)
    # Capturing user (capture-salesperson-attribution): the Odoo user who
    # made the capture, resolved Evie-side through the user-identity
    # channel (identity assertion, unique-email fallback) — out-only,
    # never edited locally; empty when the capture was anonymous or the
    # capturer matches no Odoo user (never guessed).
    captured_by_id = fields.Many2one(
        'res.users', string='Captured By', readonly=True, ondelete='set null',
        help='The Odoo user who made this capture, resolved from the Evie '
             'capturing user (identity assertion or unique email match).')
    # Marketing opt-in (privacy-lead-capture): the only consent control of
    # the capture, synced out-only as first-class consent data — its own
    # fields, never "agreed to privacy policy". The full privacy notice
    # snapshot stays Evie-side; privacy_text_version is the actionable
    # projection (which text-set version was shown).
    marketing_opt_in = fields.Boolean(
        string='Marketing Opt-in', readonly=True, tracking=True,
        help='The contact opted in to marketing mailings at capture time.')
    marketing_opt_in_at = fields.Datetime(
        string='Marketing Opt-in At', readonly=True,
        help='Timestamp of the submission carrying the opt-in outcome.')
    privacy_text_version = fields.Char(
        string='Privacy Text Version', readonly=True,
        help='Version of the Evie privacy text set shown at capture time.')
    state = fields.Selection(
        [('new', 'New'), ('to_review', 'To Review'),
         ('processed', 'Processed'), ('promoted', 'Promoted'),
         ('discarded', 'Discarded')],
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
