from odoo import fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    def action_pos_order_paid(self):
        self.ensure_one()
        res = super().action_pos_order_paid()
        self.partner_id.write(
            {
                "customer_last_order_date": fields.Datetime.now(),
                "customer_last_order_ref": self.name,
            }
        )
        return res
