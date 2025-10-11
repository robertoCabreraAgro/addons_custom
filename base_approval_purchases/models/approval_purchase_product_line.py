from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class ApprovalPurchaseProductLine(models.Model):
    """Product lines for purchase approval requests."""
    _name = "approval.purchase.product.line"
    _description = "Purchase Approval Product Line"
    _order = "sequence, id"
    _check_company_auto = True

    # ============================================================================
    # FIELDS
    # ============================================================================

    # Relations
    approval_request_purchase_id = fields.Many2one(
        "approval.request.purchase",
        string="Approval Request",
        required=True,
        ondelete="cascade"
    )

    sequence = fields.Integer(
        string="Sequence",
        default=10
    )

    # Display Type for sections and notes
    display_type = fields.Selection([
        ("line_section", "Section"),
        ("line_note", "Note")
    ], default=False, help="Technical field for UX purpose.")

    # Product Information
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        domain="[('purchase_ok', '=', True)]",
        required=lambda self: not self.display_type,
        check_company=True
    )

    product_template_id = fields.Many2one(
        "product.template",
        string="Product Template",
        related="product_id.product_tmpl_id",
        readonly=True
    )

    name = fields.Text(
        string="Description",
        compute="_compute_name",
        store=True,
        readonly=False,
        precompute=True
    )

    # Quantities and Units
    product_qty = fields.Float(
        string="Quantity",
        digits="Product Unit of Measure",
        default=1.0,
        required=True
    )

    qty_received = fields.Float(
        string="Received Qty",
        digits="Product Unit of Measure",
        copy=False,
        readonly=True
    )

    qty_invoiced = fields.Float(
        string="Invoiced Qty",
        digits="Product Unit of Measure",
        copy=False,
        readonly=True
    )

    product_uom = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        compute="_compute_product_uom",
        store=True,
        readonly=False,
        precompute=True,
        required=lambda self: not self.display_type
    )

    # Pricing
    price_unit = fields.Float(
        string="Unit Price",
        digits="Product Price",
        default=0.0
    )

    discount = fields.Float(
        string="Discount (%)",
        digits="Discount",
        default=0.0
    )

    # Taxes
    taxes_id = fields.Many2many(
        "account.tax",
        string="Taxes",
        domain="[('type_tax_use', '=', 'purchase'), ('company_id', '=', parent.company_id)]",
        check_company=True
    )

    # Computed Amounts
    price_subtotal = fields.Monetary(
        string="Subtotal",
        compute="_compute_amount",
        store=True
    )

    price_total = fields.Monetary(
        string="Total",
        compute="_compute_amount",
        store=True
    )

    price_tax = fields.Monetary(
        string="Tax",
        compute="_compute_amount",
        store=True
    )

    # Dates
    date_planned = fields.Datetime(
        string="Expected Date",
        required=True,
        default=fields.Datetime.now,
        help="Delivery date expected by vendor."
    )

    # Analytics
    analytic_distribution = fields.Json(
        string="Analytic Distribution",
        copy=True
    )

    # Company and Currency
    company_id = fields.Many2one(
        "res.company",
        related="approval_request_purchase_id.company_id",
        string="Company",
        store=True,
        readonly=True
    )

    currency_id = fields.Many2one(
        "res.currency",
        related="approval_request_purchase_id.currency_id",
        string="Currency",
        store=True,
        readonly=True
    )

    # Partner (for compatibility)
    partner_id = fields.Many2one(
        "res.partner",
        related="approval_request_purchase_id.partner_id",
        string="Partner",
        readonly=True,
        store=True
    )

    # Purchase Order Line Link (for sync)
    purchase_line_id = fields.Many2one(
        "purchase.order.line",
        string="Purchase Order Line",
        copy=False,
        readonly=True
    )

    # State
    state = fields.Selection(
        related="approval_request_purchase_id.state",
        store=True,
        readonly=True
    )

    # ============================================================================
    # COMPUTE METHODS
    # ============================================================================

    @api.depends("product_id", "display_type")
    def _compute_name(self):
        for line in self:
            if line.display_type in ("line_section", "line_note"):
                continue
            if line.product_id:
                name = line.product_id.display_name
                if line.product_id.description_purchase:
                    name += "\n" + line.product_id.description_purchase
                line.name = name
            else:
                line.name = ""

    @api.depends("product_id")
    def _compute_product_uom(self):
        for line in self:
            if line.product_id:
                line.product_uom = line.product_id.uom_po_id
            else:
                line.product_uom = False

    @api.depends("product_qty", "price_unit", "taxes_id", "discount")
    def _compute_amount(self):
        for line in self:
            if line.display_type:
                line.price_subtotal = line.price_total = line.price_tax = 0.0
                continue

            # Calculate discount
            price_unit_discounted = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            subtotal = line.product_qty * price_unit_discounted

            # Calculate taxes
            if line.taxes_id:
                tax_results = line.taxes_id.compute_all(
                    price_unit_discounted,
                    currency=line.currency_id,
                    quantity=line.product_qty,
                    product=line.product_id,
                    partner=line.partner_id
                )
                line.price_subtotal = tax_results["total_excluded"]
                line.price_total = tax_results["total_included"]
                line.price_tax = line.price_total - line.price_subtotal
            else:
                line.price_subtotal = subtotal
                line.price_total = subtotal
                line.price_tax = 0.0

    # ============================================================================
    # ONCHANGE METHODS
    # ============================================================================

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if not self.product_id:
            return

        # Update description
        self.name = self.product_id.display_name
        if self.product_id.description_purchase:
            self.name += "\n" + self.product_id.description_purchase

        # Update UOM
        self.product_uom = self.product_id.uom_po_id

        # Update price
        if self.partner_id:
            seller = self.product_id._select_seller(
                partner_id=self.partner_id,
                quantity=self.product_qty,
                date=self.approval_request_purchase_id.date_order,
                uom_id=self.product_uom
            )
            if seller:
                self.price_unit = seller.price

        # Update taxes
        if self.product_id.supplier_taxes_id:
            taxes = self.product_id.supplier_taxes_id.filtered_domain([
                ("company_id", "=", self.company_id.id)
            ])
            self.taxes_id = taxes

    @api.onchange("product_qty", "product_uom")
    def _onchange_quantity(self):
        if not self.product_id:
            return

        # Update price based on quantity
        if self.partner_id:
            seller = self.product_id._select_seller(
                partner_id=self.partner_id,
                quantity=self.product_qty,
                date=self.approval_request_purchase_id.date_order,
                uom_id=self.product_uom
            )
            if seller:
                self.price_unit = seller.price

    # ============================================================================
    # CONSTRAINTS
    # ============================================================================

    @api.constrains("product_qty")
    def _check_quantity(self):
        for line in self:
            if not line.display_type and line.product_qty <= 0:
                raise ValidationError(_("Quantity must be positive."))

    @api.constrains("price_unit")
    def _check_price(self):
        for line in self:
            if not line.display_type and line.price_unit < 0:
                raise ValidationError(_("Price cannot be negative."))

    # ============================================================================
    # BUSINESS METHODS
    # ============================================================================

    def _prepare_purchase_order_line_vals(self, order_id):
        """Prepare values for purchase order line creation."""
        self.ensure_one()

        if self.display_type:
            return {
                "order_id": order_id,
                "display_type": self.display_type,
                "name": self.name,
                "sequence": self.sequence,
                "product_qty": 0.0,
            }

        return {
            "order_id": order_id,
            "product_id": self.product_id.id,
            "name": self.name,
            "product_qty": self.product_qty,
            "product_uom": self.product_uom.id,
            "price_unit": self.price_unit,
            "discount": self.discount,
            "taxes_id": [(6, 0, self.taxes_id.ids)],
            "date_planned": self.date_planned,
            "analytic_distribution": self.analytic_distribution,
            "sequence": self.sequence,
        }

    def sync_with_purchase_line(self, purchase_line):
        """Sync data with purchase order line."""
        if not purchase_line:
            return

        # Update quantities from purchase line
        self.write({
            "qty_received": purchase_line.qty_received,
            "qty_invoiced": purchase_line.qty_invoiced,
            "purchase_line_id": purchase_line.id
        })

    def create_purchase_order_line(self, purchase_order):
        """Create purchase order line from approval line."""
        self.ensure_one()

        if self.purchase_line_id:
            raise ValidationError(_("Purchase line already created for this approval line."))

        vals = self._prepare_purchase_order_line_vals(purchase_order.id)
        purchase_line = self.env["purchase.order.line"].create(vals)

        self.purchase_line_id = purchase_line.id
        return purchase_line

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def _get_product_price_for_partner(self):
        """Get product price for the current partner."""
        self.ensure_one()

        if not self.product_id or not self.partner_id:
            return 0.0

        seller = self.product_id._select_seller(
            partner_id=self.partner_id,
            quantity=self.product_qty,
            date=self.approval_request_purchase_id.date_order,
            uom_id=self.product_uom
        )

        return seller.price if seller else self.product_id.standard_price

    def _update_taxes(self):
        """Update taxes based on product and fiscal position."""
        if not self.product_id:
            return

        taxes = self.product_id.supplier_taxes_id.filtered_domain([
            ("company_id", "=", self.company_id.id)
        ])

        # Apply fiscal position if available
        if self.approval_request_purchase_id.fiscal_position_id:
            taxes = self.approval_request_purchase_id.fiscal_position_id.map_tax(taxes)

        self.taxes_id = taxes