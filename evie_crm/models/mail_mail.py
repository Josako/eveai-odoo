"""Idempotency anchor for Evie-composed messages on Odoo mail.mail."""

from odoo import fields, models


class MailMail(models.Model):
    _inherit = 'mail.mail'

    x_evie_delivery_key = fields.Char(
        string='Evie Delivery Key',
        index=True,
        copy=False,
        readonly=True,
        help="Random key assigned by Evie before provider submission. Used to "
             "adopt and reconcile a remote mail after an uncertain outcome.",
    )

    # Multiple NULL keys are allowed; a confirmed delivery key is globally
    # unique and prevents blind duplicate creation after a lost response.
    _x_evie_delivery_key_uniq = models.Constraint(
        'unique(x_evie_delivery_key)',
        'An Odoo mail with this Evie Delivery Key already exists.',
    )
