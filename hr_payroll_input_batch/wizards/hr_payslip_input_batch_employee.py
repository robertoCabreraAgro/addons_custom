from odoo import fields, models


class HrPayslipInputBatchEmployees(models.TransientModel):
    _name = "hr.payslip.input.batch.employee"
    _description = "Generate payslip extras for all selected employees"

    employee_ids = fields.Many2many("hr.employee", string="Employees")

    def load_employees(self):
        active_id = self.env.context.get("active_id")
        detail = self.env["hr.payslip.input.batch.detail"]
        for employee in self.employee_ids:
            detail.create({"employee_id": employee.id, "extra_id": active_id})
        return {"type": "ir.actions.act_window_close"}
