from odoo import fields, models


class StockLocation(models.Model):
    """Inherit StockLocation"""

    _inherit = "stock.location"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    removal_priority = fields.Integer(
        default=10,
        help="This priority applies when removing stock and incoming dates are equal.",
    )
