from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        res = super().action_confirm()
        for order in self:
            order.partner_id.write(
                {
                    "customer_last_order_date": fields.Datetime.now(),
                    "customer_last_order_ref": order.name,
                }
            )
        return res
