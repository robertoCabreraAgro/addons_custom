from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HrPayslipOvertime(models.Model):
    _name = "hr.payslip.overtime"
    _description = "Pay Slip overtime"
    _order = "name"

    name = fields.Date(
        "Date",
        required=True,
        help="Indicate the date for the overtime",
    )
    payslip_id = fields.Many2one(
        "hr.payslip",
        ondelete="cascade",
        help="Payslip related.",
    )
    hours = fields.Integer(
        help="Number of overtime hours worked in the period",
    )
    is_simple = fields.Boolean(
        help="Indicate if this overtime must be paid like simple.",
    )
    employee_id = fields.Many2one(
        "hr.employee",
        help="Indicate the employee to this overtime.",
    )
    week = fields.Integer(
        compute="_compute_week",
        store=True,
        help="Saves the week number to compute the exempt amount.",
    )

    @api.depends("name")
    def _compute_week(self):
        for record in self:
            record.week = record.name.isocalendar()[1] if record.name else False

    @api.ondelete(at_uninstall=False)
    def _unlink_except_state_done(self):
        if self.filtered(lambda o: o.payslip_id.state == "done"):
            raise UserError(_("You cannot delete an overtime which payroll has been posted once."))
