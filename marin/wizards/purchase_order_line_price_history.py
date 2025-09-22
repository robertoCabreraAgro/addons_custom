from odoo import Command, api, fields, models


class PurchaseOrderLinePriceHistory(models.TransientModel):
    _name = "purchase.order.line.price.history"
    _description = "Purchase order line price history"

    line_id = fields.Many2one(
        comodel_name="purchase.order.line",
        string="Purchase order line",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Supplier",
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product",
    )
    line_ids = fields.One2many(
        comodel_name="purchase.order.line.price.history.line",
        inverse_name="wizard_id",
        string="Historical lines",
        readonly=True,
    )
    include_rfq = fields.Boolean(
        string="Include Request for Quotations",
    )

    def _prepare_domain(self):
        states = ["purchase", "done"]
        states += ["draft", "sent", "to approve"] if self.include_rfq else states
        domain = [("state", "in", states)]
        if self.partner_id:
            commercial_ids = self.partner_id.commercial_partner_id.ids
            domain += [("partner_id", "child_of", commercial_ids)]
        if self.product_id:
            domain += [("product_id", "=", self.product_id.id)]
        return domain

    def _set_line_ids(self, domain):
        vals = []
        lines = self.env["purchase.order.line"].search(
            domain, order="id desc", limit=10
        )
        lines -= self.line_id
        for line in lines:
            vals.append(Command.create({"line_id": line.id}))
        self.line_ids = vals

    @api.onchange("partner_id", "product_id", "include_rfq")
    def _onchange_partner_id(self):
        self.line_ids = False
        if not (self.partner_id and self.product_id):
            return
        domain = self._prepare_domain()
        self._set_line_ids(domain)


class PurchaseOrderLinePriceHistoryLine(models.TransientModel):
    _name = "purchase.order.line.price.history.line"
    _description = "Purchase order line price history line"

    wizard_id = fields.Many2one(
        comodel_name="purchase.order.line.price.history",
        string="Wizard",
    )
    line_id = fields.Many2one(
        comodel_name="purchase.order.line",
        string="Purchase order line",
    )
    order_id = fields.Many2one(
        related="line_id.order_id",
    )
    partner_id = fields.Many2one(
        related="line_id.partner_id",
    )
    date = fields.Datetime(
        related="line_id.order_id.date_order",
    )
    qty = fields.Float(
        related="line_id.product_uom_qty",
    )
    price_unit = fields.Float(
        related="line_id.price_unit",
    )
    tax_ids = fields.Many2many(
        related="line_id.tax_ids",
    )

    def _prepare_vals(self):
        return {"price_unit": self.price_unit}

    def action_set_price(self):
        self.wizard_id.purchase_order_line_id.write(self._prepare_vals())
