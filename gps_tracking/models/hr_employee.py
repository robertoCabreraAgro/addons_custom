from odoo import fields, models

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    enable_vehicle_loan = fields.Boolean(
        string="Enable Vehicle Loan Report",
        default=False,
        help="If checked, this employee's trips will be included in the vehicle loan report."
    )
