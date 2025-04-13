from odoo import models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _prepare_aml_vals(self, **optional_values):
        vals = super()._prepare_aml_vals(**optional_values)
        vals["purchase_price"] = self.sudo().purchase_price
        return vals
