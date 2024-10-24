from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"


    purchase_price = fields.Float(
        string="Cost",
        digits="Product Price",
        compute="_compute_purchase_price", store=True,
        readonly=False,
    )
    margin = fields.Float(
        digits="Product Price",
        compute="_compute_margin", store=True,
    )
    margin_signed = fields.Float(
        digits="Product Price",
        compute="_compute_margin", store=True,
    )
    margin_percent = fields.Float(
        string="Margin (%)",
        digits="Product Price",
        compute="_compute_margin", store=True,
        readonly=True
    )


    def _get_purchase_price(self):
        self.ensure_one()
        return self.product_id.standard_price

    @api.depends("product_id", "product_uom_id")
    def _compute_purchase_price(self):
        for line in self:
            if not line.move_id.is_invoice():
                continue
            if line.move_id.is_sale_document():
                purchase_price = line._get_purchase_price()
                if line.product_uom_id != line.product_id.uom_id:
                    purchase_price = line.product_id.uom_id._compute_price(
                        purchase_price, line.product_uom_id
                    )
                move = line.move_id
                company = move.company_id or self.env.company
                line.purchase_price = company.currency_id._convert(
                    purchase_price,
                    move.currency_id,
                    company,
                    move.invoice_date or fields.Date.today(),
                    round=False,
                )
            else:
                line.purchase_price = 0.0

    @api.depends("purchase_price", "price_subtotal")
    def _compute_margin(self):
        for line in self.filtered(
            lambda l:
                l.move_id.is_sale_document()
                and l.display_type == 'product'
        ):
            margin = line.price_subtotal - (line.purchase_price * line.quantity)
            sign = -1 if line.move_id.move_type == "out_refund" else 1
            line.update(
                {
                    "margin": margin,
                    "margin_signed": margin * sign,
                    "margin_percent": (
                        margin / line.price_subtotal * 100.0
                        if line.price_subtotal
                        else 0.0
                    ),
                }
            )
