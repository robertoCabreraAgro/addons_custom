from odoo import api, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.depends("purchase_price", "price_subtotal")
    def _compute_margin(self):
        invoice_lines_with_downpayment = self.filtered(
            lambda x: any(x.sale_line_ids.mapped("is_downpayment"))
        )
        invoice_lines_with_downpayment.update(
            {
                "margin": 0.0,
                "margin_signed": 0.0,
                "margin_percent": 0.0,
            }
        )
        super(AccountMoveLine, self - invoice_lines_with_downpayment)._compute_margin()
