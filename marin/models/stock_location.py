from odoo import fields, models


class StockLocation(models.Model):
    _inherit = "stock.location"

    removal_priority = fields.Integer(
        default=10,
        help="This priority applies when removing stock and incoming dates are equal.",
    )

    def should_bypass_reservation(self):
        res = super().should_bypass_reservation()
        if self.usage == "transit" and not self.company_id:
            res = False
        return res
