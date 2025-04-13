from odoo import api, fields, models


class PosOrderLine(models.Model):
    """Inherit PosOrderLine"""

    _inherit = "pos.order.line"

    # New fields
    price_cost = fields.Float(
        "Cost",
        "Product Price",
    )
    margin = fields.Monetary(
        compute="_compute_margin",
        store=True,
    )
    margin_percent = fields.Float(
        string="Margin (%)",
        digits=(12, 4),
        compute="_compute_margin",
        store=True,
    )

    # Override original method
    def _compute_total_cost(self, stock_moves):
        # TODO: Improve this process as we are computing the product_cost on the original and this one
        # And check if is possible to use sql views instead of computing this new field price_cost
        res = super()._compute_total_cost(stock_moves)
        for line in self.filtered(lambda l: not l.is_total_cost_computed):
            product = line.product_id
            if line._is_product_storable_fifo_avco() and stock_moves:
                product_cost = product._compute_average_price(
                    0, line.qty, self._get_stock_moves_to_consider(stock_moves, product)
                )
            else:
                product_cost = product.standard_price
            line.price_cost = product_cost
        return res
