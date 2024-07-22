from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    loan_generate_breakdown = fields.Boolean(
        "Generate loan breakdown on payslip reports?",
        help="If checked, a breakdown of the employee's loans will be provided on printed payslip reports",
    )
