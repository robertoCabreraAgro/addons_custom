from odoo import fields, models


class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    enable_vehicle_loan = fields.Boolean(
        string="Enable Vehicle Loan Report",
        default=False,
        help="If checked, this employee's trips will be included in the vehicle loan report.",
    )

    def action_enable_vehicle_loan_report(self):
        """Server action to enable vehicle loan report for selected employees."""
        self.write({"enable_vehicle_loan": True})
        return True

    def action_disable_vehicle_loan_report(self):
        """Server action to disable vehicle loan report for selected employees."""
        self.write({"enable_vehicle_loan": False})
        return True
