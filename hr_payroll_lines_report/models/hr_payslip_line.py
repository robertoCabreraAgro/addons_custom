from odoo import fields, models


class HrPayslipLine(models.Model):
    _inherit = "hr.payslip.line"

    payslip_name = fields.Char(related="slip_id.name")
    payslip_number = fields.Char(related="slip_id.number", string="Payslip Reference")
    registration_number = fields.Char(related="employee_id.registration_number", store=True)
    struct_id = fields.Many2one(related="slip_id.struct_id", store=True)
    work_location_id = fields.Many2one(related="employee_id.work_location_id", store=True)
    department_id = fields.Many2one(related="slip_id.department_id", store=True)
    payslip_run_id = fields.Many2one(related="slip_id.payslip_run_id", store=True)
