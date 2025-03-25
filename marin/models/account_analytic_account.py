from odoo import fields, models


class AccountAnalyticLineInherit(models.Model):
    _inherit = "account.analytic.line"

    date_impacted = fields.Date(
        string="Date impacted",
        required=True,
        default=fields.Date.context_today,
        index=True,
    )
    amount_taxinc = fields.Monetary(
        string="Amount Tax included",
        required=True,
        default=0.0,
    )
