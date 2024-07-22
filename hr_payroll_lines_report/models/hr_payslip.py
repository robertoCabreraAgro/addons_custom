from odoo import fields, models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    work_location_id = fields.Many2one(related="employee_id.work_location_id", store=True)
