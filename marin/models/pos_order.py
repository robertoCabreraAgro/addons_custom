from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    margin = fields.Monetary(compute="_compute_margin", store=True)
    margin_percent = fields.Float(string="Margin (%)", compute="_compute_margin", digits=(12, 4), store=True)
    is_total_cost_computed = fields.Boolean(compute="_compute_is_total_cost_computed", store=True)

    # This is a fix for this method
    @api.model
    def _amount_line_tax(self, line, fiscal_position_id):
        if line.tax_ids:
            return super()._amount_line_tax(line, fiscal_position_id)
        return 0.0

    def get_delivery_info(self):
        picking = self.env["stock.picking"].search(
            [
                ("pos_order_id", "=", self.id),
            ],
            limit=1,
        )
        if not picking:
            return []
        lines = self.env["stock.move.line"].search(
            [
                ("picking_id", "=", picking.id),
            ]
        )
        return [
            {
                "id": line.id,
                "from": line.location_id.name,
                "lot": line.lot_id.name,
                "done": line.quantity,
                "product": line.product_id.display_name,
            }
            for line in lines
        ]
