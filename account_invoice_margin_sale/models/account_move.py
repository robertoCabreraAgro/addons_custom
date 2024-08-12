from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_margin_applicable_lines(self):
        invoice_lines = super()._get_margin_applicable_lines()
        return invoice_lines.filtered(
            lambda l: not any(l.sale_line_ids.mapped("is_downpayment"))
        )
