from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        """Override to add credit validation before confirming sale order"""
        for order in self:
            # Validate credit status of the partner
            order.partner_id._validate_credit_checks(
                payment_term=order.payment_term_id
            )

        # Call the original method
        return super(SaleOrder, self).action_confirm()
