from odoo import Command, api, fields, models


class SaleOrderLinePriceHistory(models.TransientModel):
    _name = "sale.order.line.price.history"
    _description = "Sale order line price history"

    line_id = fields.Many2one("sale.order.line", "Sale order line")
    partner_id = fields.Many2one("res.partner", "Customer")
    product_id = fields.Many2one("product.product", "Product")
    line_ids = fields.One2many("sale.order.line.price.history.line", "wizard_id", "Historical lines", readonly=True)
    include_quotations = fields.Boolean()

    @api.onchange("partner_id", "product_id", "include_quotations")
    def _onchange_partner_id(self):
        self.line_ids = False
        states = ["sale", "done"]
        states += ["draft", "sent"] if self.include_quotations else states
        domain = [("product_id", "=", self.product_id.id), ("state", "in", states)]
        if self.partner_id:
            domain += [("order_partner_id", "child_of", self.partner_id.commercial_partner_id.ids)]
        vals = []
        lines = self.env["sale.order.line"].search(domain, order="id desc", limit=10)
        lines -= self.line_id
        for line in lines:
            vals.append(Command.create({"line_id": line.id}))
        self.line_ids = vals


class SaleOrderLinePriceHistoryline(models.TransientModel):
    _name = "sale.order.line.price.history.line"
    _description = "Sale order line price history line"

    wizard_id = fields.Many2one("sale.order.line.price.history", "Wizard")
    line_id = fields.Many2one("sale.order.line", "Sale order line")
    order_id = fields.Many2one(related="line_id.order_id")
    partner_id = fields.Many2one(related="line_id.order_partner_id")
    date = fields.Datetime(related="line_id.order_id.date_order")
    qty = fields.Float(related="line_id.product_uom_qty")
    price_unit = fields.Float(related="line_id.price_unit")
    discount = fields.Float(related="line_id.discount")

    def _prepare_vals(self):
        return {"price_unit": self.price_unit, "discount": self.discount}

    def action_set_price(self):
        self.wizard_id.line_id.write(self._prepare_vals())
