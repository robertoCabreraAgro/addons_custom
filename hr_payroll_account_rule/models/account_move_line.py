from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    salary_rule_id = fields.Many2one(
        "hr.salary.rule",
        string="Rule",
        help="Saves the rule origin from this item, if the entry comes from a payslip",
    )
