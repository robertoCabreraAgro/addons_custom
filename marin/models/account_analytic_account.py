from odoo import fields, models


class AccountAnalyticLineInherit(models.Model):
    _inherit = "account.analytic.line"

    date_impacted = fields.Date("Date impacted", required=True, index=True, default=fields.Date.context_today)
    amount_taxinc = fields.Monetary("Amount Tax included", required=True, default=0.0)
