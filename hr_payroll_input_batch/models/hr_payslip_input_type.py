from odoo import fields, models


class HrPayslipInputType(models.Model):
    _inherit = "hr.payslip.input.type"

    active = fields.Boolean(default=True)
