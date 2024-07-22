from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HrEmployeeLoanLine(models.Model):
    _name = "hr.employee.loan.line"
    _description = "Allow register the loans in each employee."

    sequence = fields.Integer()
    loan_id = fields.Many2one("hr.employee.loan")
    payslip_id = fields.Many2one(
        related="payslip_line_id.slip_id",
    )
    payslip_line_id = fields.Many2one(
        "hr.payslip.line",
        readonly=True,
    )
    state = fields.Selection(
        related="loan_id.state",
        store=True,
    )
    name = fields.Char()
    date = fields.Date(
        help="Informative field to indicate when is expected to by applied this loan.",
    )
    amount = fields.Float(
        digits="Payroll Loan",
        help="How much should be deducted at this point.",
    )
    cumulative_amount = fields.Float(
        compute="_compute_cumulative_and_remaining_amount",
        digits="Payroll Loan",
        help="How much the has been deducted at this point.",
    )
    remaining_amount = fields.Float(
        compute="_compute_cumulative_and_remaining_amount",
        digits="Payroll Loan",
        help="How much the has been deducted at this point.",
    )

    @api.depends("loan_id.loan_line_ids")
    def _compute_cumulative_and_remaining_amount(self):
        for record in self:
            lines = record.loan_id.loan_line_ids.sorted(key=lambda l: l.sequence).filtered(
                lambda l: l.sequence < record.sequence
            )
            record.cumulative_amount = record.amount + (lines[-1].cumulative_amount if lines else 0)
            if record.loan_id._is_timeless():
                record.remaining_amount = 0
                continue
            record.remaining_amount = (
                record.loan_id.total_amount if not lines else (lines[-1].remaining_amount)
            ) - record.amount

    @api.ondelete(at_uninstall=False)
    def _unlink_except_close_or_draft(self):
        if self.filtered(lambda l: l.payslip_id and l.loan_id.state not in ["close", "draft"]):
            raise UserError(_("Only lines without payslip related could be removed."))

    @api.model_create_multi
    def create(self, vals_list):
        for num, vals in enumerate(vals_list):
            if vals.get("loan_id"):
                loan = self.env["hr.employee.loan"].browse(vals["loan_id"])
                vals["sequence"] = len(loan.loan_line_ids) + num + 1
        return super().create(vals_list)
