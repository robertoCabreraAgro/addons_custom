from odoo import fields, models


class HrSalaryRule(models.Model):
    _name = "hr.salary.rule"
    _inherit = ["hr.salary.rule", "mail.thread", "mail.activity.mixin"]

    analytic_account_id = fields.Many2one(tracking=True)
    account_debit = fields.Many2one(tracking=True)
    account_credit = fields.Many2one(tracking=True)
    not_computed_in_net = fields.Boolean(tracking=True)
    partner_id = fields.Many2one(tracking=True)
