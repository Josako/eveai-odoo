from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    x_evie_brief_seen_on = fields.Date(
        string='Evie Brief Seen On', copy=False,
        help="Local day the morning brief last popped up on its own (kept on "
             "the user so it does not pop up again on another device).",
    )
