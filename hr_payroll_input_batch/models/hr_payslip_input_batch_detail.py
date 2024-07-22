from odoo import fields, models


class HrPayslipInputBatchDetail(models.Model):
    _name = "hr.payslip.input.batch.detail"
    _description = "Detail for each extra inputs"

    name = fields.Char(help="Indicate the detail for this input.\nExample: Commission SO1234")
    employee_id = fields.Many2one("hr.employee", "Employee", required=True)
    amount = fields.Float()
    extra_id = fields.Many2one("hr.payslip.input.batch")
