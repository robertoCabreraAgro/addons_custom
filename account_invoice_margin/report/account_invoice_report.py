from odoo import fields, models
from odoo.tools import SQL


class AccountInvoiceReport(models.Model):
    _inherit = "account.invoice.report"

    margin = fields.Float(readonly=True)

    def _select(self):
        return SQL("%s, line.margin_signed AS margin", super()._select())
