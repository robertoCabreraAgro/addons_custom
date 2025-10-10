from odoo import api, fields, models


class ApprovalPurchaseProductLine(models.Model):
    """Product lines for purchase order approval requests."""
    _name = "approval.purchase.product.line"
    _description = "Purchase Approval Product Line"
    _order = "sequence, id"

    name = fields.Char()
    sequence = fields.Integer()
    product_id = fields.Many2one()
    product_qty = fields.Float()
    price_unit = fields.Float()
    price_subtotal = fields.Monetary()
    currency_id = fields.Many2one()
    approval_request_purchase_id = fields.Many2one()
    purchase_line_id = fields.Many2one()

    @api.depends("product_qty", "price_unit")
    def _compute_price_subtotal(self):
        """Compute the subtotal amount for the line."""
        pass