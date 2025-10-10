from odoo import api, fields, models


class ApprovalRequestPurchase(models.Model):
    """Purchase Order approval request model."""
    _name = "approval.request.purchase"
    _description = "Purchase Order Approval Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char()
    purchase_order_id = fields.Many2one()
    approval_request_id = fields.Many2one()
    product_line_ids = fields.One2many()
    amount_total = fields.Monetary()
    currency_id = fields.Many2one()
    state = fields.Selection()

    def action_request_approval(self):
        """Submit purchase order for approval."""
        pass

    def action_approve(self):
        """Approve the purchase order request."""
        pass

    def action_refuse(self):
        """Refuse the purchase order request."""
        pass