from odoo import api, fields, models


class SaleTargetLine(models.Model):
    """Sales target lines with product details and calculated quantities.

    Each line represents a product target with quantities calculated based on
    template quantities, customer hectares, and profile factors.
    """

    _name = "sale.target.line"
    _description = "Sales Target Line"
    _order = "target_id, product_id"

    target_id = fields.Many2one(
        "sale.target",
        string="Sales Target",
        required=True,
        ondelete="cascade",
        help="Related sales target record",
    )

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        help="Product for this target line",
    )

    price_unit = fields.Monetary(
        string="Unit Price",
        currency_field="currency_id",
        help="Unit price for target amount calculation",
    )

    quantity = fields.Float(string="Template Quantity", help="Base quantity from quotation template")

    subtotal = fields.Monetary(
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
        help="Calculated as unit price × target quantity",
    )

    target_quantity = fields.Float(
        string="Quantity",
        compute="_compute_target_quantity",
        store=True,
        help="Calculated as template quantity × hectares × profile factor",
    )

    target_amount = fields.Monetary(
        string="Amount",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
        help="Calculated as unit price × target quantity",
    )

    currency_id = fields.Many2one("res.currency", related="target_id.currency_id", readonly=True)

    @api.depends("quantity", "target_id.hectares", "target_id.factor")
    def _compute_target_quantity(self):
        """Calculate target quantity as template quantity × hectares × profile factor."""
        for line in self:
            hectares = line.target_id.hectares or 0.0
            factor = line.target_id.factor or 1.0
            quantity = line.quantity or 0.0
            line.target_quantity = quantity * hectares * factor

    @api.depends("price_unit", "target_quantity")
    def _compute_amounts(self):
        """Calculate subtotal and target amount based on price and quantities."""
        for line in self:
            line.subtotal = line.price_unit * line.target_quantity
            line.target_amount = line.price_unit * line.target_quantity
