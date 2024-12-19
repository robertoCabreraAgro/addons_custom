from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = "account.account"

    x_sequence = fields.Integer(
        help="Field introduced to keep custom order when reordering accounts at migration"
    )
