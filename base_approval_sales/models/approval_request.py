from odoo import api, fields, models


class ApprovalRequest(models.Model):
    """Extend approval request for sales order integration."""
    _inherit = "approval.request"

    # Link to sale order if this request is for a sale order
    sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Sale Order",
        help="Related sale order for this approval request",
    )

    @api.model
    def create(self, vals):
        """Override create to link sale order if reference matches."""
        request = super().create(vals)

        # Try to link with sale order if reference matches
        if request.reference:
            sale_order = self.env["sale.order"].search([
                ("name", "=", request.reference)
            ], limit=1)
            if sale_order:
                request.sale_order_id = sale_order.id

        return request