from odoo import api, fields, models


class SaleTargetLine(models.Model):
    """Sales target lines with product details and calculated quantities.

    Each line represents a product target with quantities calculated based on
    template quantities, customer hectares, and profile factors.
    """

    _name = "sale.target.line"
    _description = "Sales Target Line"
    _order = "target_id, product_id"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

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

    quantity = fields.Float(
        string="Template Quantity", help="Base quantity from quotation template"
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

    currency_id = fields.Many2one(
        "res.currency", related="target_id.currency_id", readonly=True
    )

    # Related fields from target_id
    partner_id = fields.Many2one(
        "res.partner",
        related="target_id.partner_id",
        string="Customer",
        store=True,
        readonly=True,
    )
    user_id = fields.Many2one(
        "res.users",
        related="target_id.user_id",
        string="Salesperson",
        store=True,
        readonly=True,
    )
    season_id = fields.Many2one(
        "date.range",
        related="target_id.season_id",
        string="Season",
        store=True,
        readonly=True,
    )
    profile_id = fields.Many2one(
        "res.partner.profile",
        related="target_id.profile_id",
        string="Profile",
        store=True,
        readonly=True,
    )
    hectares = fields.Float(
        related="target_id.hectares", string="Hectares", store=True, readonly=True
    )
    template_id = fields.Many2one(
        "sale.order.template",
        related="target_id.template_id",
        string="Template",
        store=True,
        readonly=True,
    )

    sold_amount = fields.Monetary(
        string="Sold Amount",
        compute="_compute_sold_amount",
        store=True,
        currency_field="currency_id",
        help="Amount sold for this product with same customer, salesperson and season",
    )

    gap_amount = fields.Monetary(
        string="Gap Amount",
        compute="_compute_gap_amount",
        store=True,
        currency_field="currency_id",
        help="Amount remaining to reach target (target_amount - sold_amount)",
    )

    target_percentage = fields.Float(
        string="Target %",
        compute="_compute_target_percentage",
        store=True,
        aggregator="avg",
        help="Percentage of target completion (sold_amount / target_amount * 100)",
    )

    manufacturer_id = fields.Many2one(
        "res.partner",
        string="Manufacturer",
        compute="_compute_manufacturer_id",
        store=True,
        help="Manufacturer of the product in this target line.",
    )

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
            line.target_amount = line.price_unit * line.target_quantity

    def _get_historical_orders(self):
        """Get historical orders for current line's parameters."""
        if not all([self.partner_id, self.user_id, self.season_id]):
            return self.env["sale.order"]

        return self.env["sale.order"].search(
            [
                ("partner_id", "=", self.partner_id.id),
                ("user_id", "=", self.user_id.id),
                ("season_id", "=", self.season_id.id),
                ("state", "in", ["sale", "done"]),
            ]
        )

    @api.depends("product_id", "partner_id", "user_id", "season_id")
    def _compute_sold_amount(self):
        """Calculate sold amount for this product with same customer, salesperson and season."""
        for line in self:
            if not all(
                [line.product_id, line.partner_id, line.user_id, line.season_id]
            ):
                line.sold_amount = 0.0
                continue

            historical_orders = line._get_historical_orders()
            sold_total = 0.0
            for order in historical_orders:
                for order_line in order.line_ids:
                    if order_line.product_id.id == line.product_id.id:
                        sold_total += order_line.price_subtotal

            line.sold_amount = sold_total

    @api.depends("target_amount", "sold_amount")
    def _compute_gap_amount(self):
        """Calculate gap amount as target_amount - sold_amount."""
        for line in self:
            line.gap_amount = line.target_amount - line.sold_amount

    @api.depends("target_amount", "sold_amount")
    def _compute_target_percentage(self):
        """Calculate target completion percentage (capped at 100%)."""
        for line in self:
            if line.target_amount > 0:
                percentage = (line.sold_amount / line.target_amount) * 100
                line.target_percentage = min(percentage, 100.0)
            else:
                line.target_percentage = 0.0

    @api.depends("product_id", "product_id.manufacturer_id")
    def _compute_manufacturer_id(self):
        """Compute manufacturer from the related product.
        This allows filtering and grouping sales targets by manufacturer
        for production planning purposes.
        """
        for line in self:
            line.manufacturer_id = (
                line.product_id.manufacturer_id if line.product_id else False
            )
