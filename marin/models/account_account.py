from odoo import fields, models


class AccountAccount(models.Model):
    """Inherit AccountAccount"""

    _inherit = "account.account"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    x_sequence = fields.Integer(
        help="Field introduced to keep custom order when reordering accounts at migration",
    )
