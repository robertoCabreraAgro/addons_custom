from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    loan_ids = fields.One2many(
        "hr.employee.loan",
        "employee_id",
        "Loans",
        help="Indicate the loans for the employee. Will be considered on the payslips.",
    )
    loan_count = fields.Integer(
        compute="_compute_loan_count",
        groups="hr_payroll.group_hr_payroll_user",
        help="Techincal field to know if the loan is fully paid.",
    )

    @api.depends("loan_ids")
    def _compute_loan_count(self):
        for employee in self:
            employee.loan_count = len(employee.loan_ids)
