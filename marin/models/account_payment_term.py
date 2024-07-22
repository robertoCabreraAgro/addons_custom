from odoo import api, fields, models


class AccountPaymentTerm(models.Model):
    _inherit = "account.payment.term"

    is_immediate = fields.Boolean(
        "Immediate payment term", compute="_compute_is_immediate_payment_term", readonly=True
    )

    @api.depends("line_ids")
    def _compute_is_immediate_payment_term(self):
        for record in self:
            lines = record.line_ids
            period = sum(lines.mapped("nb_days"))
            record.is_immediate = not period
