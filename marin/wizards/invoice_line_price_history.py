from odoo import Command, api, fields, models


class InvoiceLinePriceHistory(models.TransientModel):
    _name = "invoice.line.price.history"
    _description = "Invoice Line price history"

    line_id = fields.Many2one("account.move.line", "Invoice Line")
    partner_id = fields.Many2one("res.partner", "Partner")
    product_id = fields.Many2one("product.product", "Product")
    line_ids = fields.One2many(
        comodel_name="invoice.line.price.history.line",
        inverse_name="wizard_id",
        string="Historical lines",
        readonly=True,
    )
    include_draft = fields.Boolean("Include Draft Moves")

    @api.onchange("partner_id", "product_id", "include_draft", "line_id")
    def _onchange_partner_id(self):
        self.line_ids = False
        if not self.product_id:
            return
        move_type = self.line_id.move_id.move_type
        states = ["posted"]
        if self.include_draft:
            states += ["draft"]
        domain = [
            ("product_id", "=", self.product_id.id),
            ("parent_state", "in", states),
            ("move_id.move_type", "=", move_type),
        ]
        if self.partner_id:
            commercial_ids = self.partner_id.commercial_partner_id.ids
            domain += [("partner_id", "child_of", commercial_ids)]
        vals = []
        lines = self.env["account.move.line"].search(domain, order="id desc", limit=20)
        lines -= self.line_id
        for line in lines:
            vals.append(Command.create({"line_id": line.id}))
        self.line_ids = vals


class InvoiceLinePriceHistoryLine(models.TransientModel):
    _name = "invoice.line.price.history.line"
    _description = "Invoice Line price history line"

    wizard_id = fields.Many2one("invoice.line.price.history", "Wizard")
    line_id = fields.Many2one("account.move.line", "Invoice Line")
    move_id = fields.Many2one(related="line_id.move_id")
    partner_id = fields.Many2one(related="line_id.partner_id")
    date = fields.Date(related="line_id.date")
    qty = fields.Float(related="line_id.quantity")
    price_unit = fields.Float(related="line_id.price_unit")
    discount = fields.Float(related="line_id.discount")
    tax_ids = fields.Many2many(related="line_id.tax_ids")

    def _prepare_vals(self):
        return {"price_unit": self.price_unit, "discount": self.discount}

    def action_set_price(self):
        self.wizard_id.line_id.write(self._prepare_vals())
