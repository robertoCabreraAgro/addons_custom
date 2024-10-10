from dateutil.relativedelta import relativedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class HrEmployeeLoan(models.Model):
    _name = "hr.employee.loan"
    _description = "Allow register the loans in each employee."
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        "Number",
        required=True,
        tracking=True,
        help="Id number or description for this loan",
    )
    amount = fields.Float(
        tracking=True,
        digits="Payroll Loan",
        help="Indicates the Amount to withhold. Select a loan type (input type) to get more information about "
        "the amount value that is expected.",
    )
    total_amount = fields.Float(
        compute="_compute_total_amount",
        inverse="_inverse_total_amount",
        store=True,
        tracking=True,
        digits="Payroll Loan",
        help="Indicates the total loan amount to be paid. If it is 0, the amount is not defined.",
    )
    payment_term = fields.Integer(
        tracking=True,
        help='Indicates the payment term for this loan. If is undefined, please use "-1".',
    )
    payslip_ids = fields.Many2many(
        "hr.payslip",
        string="Payslips",
        tracking=True,
        copy=False,
        help="Payslips where this loan is collected.",
    )
    payslips_count = fields.Integer(
        "Number of Payslips",
        compute="_compute_payslips_count",
        tracking=True,
    )
    loan_line_ids = fields.One2many(
        "hr.employee.loan.line",
        "loan_id",
        string="Loan Lines",
        help="Loan lines, they represent the loan table of amortization, how the loan amounts will be deducted.",
    )
    loan_line_count = fields.Float(
        compute="_compute_loan_line_count_and_amount_paid",
        help="Number of loan lines. Technical field designed to assist views.",
    )
    amount_paid = fields.Float(
        compute="_compute_loan_line_count_and_amount_paid",
        digits="Payroll Loan",
        help="Sum of loan payments on the slips.",
    )
    amount_remaining = fields.Float(
        compute="_compute_amount_remaining",
        digits="Payroll Loan",
        help="Remaining value based on the amount total and amount paid.",
    )
    employee_id = fields.Many2one(
        "hr.employee",
        tracking=True,
        help="Employee for this loan",
    )
    active = fields.Boolean(
        default=True,
        tracking=True,
        help="If the loan was paid the record will be deactivated.",
    )
    date_from = fields.Date(
        required=True,
        help="Start date of loan, is used to know if must be considered in the payslip.",
    )
    date_to = fields.Date(
        help="End date of loan, is used to know if must be considered in the payslip.\nNote: If is empty will be "
        "considered always.",
    )
    company_id = fields.Many2one(
        related="employee_id.company_id",
        help="Employee Company",
    )
    input_type_id = fields.Many2one(
        "hr.payslip.input.type",
        "Input to define in the payslips",
        tracking=True,
        domain="[('use_in_loan', '=', True)]",
        help="This input will be used to search the loan in the salary rules code",
    )
    input_type_loan_note = fields.Char(related="input_type_id.loan_note")
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("verify", "Verify"),
            ("active", "Running"),
            ("unlocked", "Unlocked"),
            ("close", "Close / Expired"),
        ],
        copy=False,
        default="draft",
        tracking=True,
        help="Loans state.\n Draft: Represents a new loan that has not been calculated its table.\n"
        "Verified: A loan that was already calculated and can be validated to start the deduction on the payroll.\n"
        "Running: A valid loan that is active and will be considered on the payslips calculation.\n"
        "Unlocked: A loan that is being edited by user or that is not valid anymore and needs user intervention. "
        "If a loan is in this state, it will not be considered on the payslip calculation.\n"
        "Close / Expired: This state represents that the loan is already finished, closed or canceled, and will "
        "not be considered by payslips calculation anymore.",
    )
    error_message = fields.Char(
        help="Technical field used to show the user, with an alert warning box, that the "
        "loan needs his intervention.",
    )
    interest_percent = fields.Float(
        tracking=True,
        help="Set the interest percent that will be charged for the requested loan.",
    )
    allows_interest_payment = fields.Boolean(related="input_type_id.allows_interest_payment")

    @api.depends("payslip_ids")
    def _compute_payslips_count(self):
        for loan in self:
            loan.payslips_count = len(loan.payslip_ids.filtered(lambda rec: rec.state == "done"))

    @api.depends("loan_line_ids")
    def _compute_loan_line_count_and_amount_paid(self):
        for loan in self:
            lines = loan.loan_line_ids
            loan.loan_line_count = len(lines)
            loan.amount_paid = sum(lines.filtered(lambda l: l.payslip_id.state == "done").mapped("amount"))

    @api.depends("total_amount", "amount_paid")
    def _compute_amount_remaining(self):
        for loan in self:
            loan.amount_remaining = loan.total_amount - loan.amount_paid

    @api.depends("amount", "payment_term")
    def _compute_total_amount(self):
        for record in self:
            if record._is_timeless():
                record.total_amount = 0
                continue
            record.total_amount = record.amount * record.payment_term

    @api.ondelete(at_uninstall=False)
    def _unlink_except_close_draft(self):
        if self.filtered(lambda l: l.state not in ["close", "draft"]):
            raise UserError(_("Only loans on draft or close state could be removed."))

    def compute_sheet(self):
        """This method creates the loan amortization table according to its characteristics.
        This method will be called just in stated draft and verify.
        If the loan is timeless (the loan lines number are not defined), do not calculate the table, keep empty.
        1. Delete the old table.
        2. Get values list to create the lines, with its amount, date, and sequence.
        The sequence will be used by other methods to order and ensure were are using the correct loan line.
        3. Call compute amount to make sure the accumulative and remaning amount is calculated correctly
        before continue.
        """
        self.loan_line_ids.unlink()

        records = self.filtered(lambda l: l.state in ["draft", "verify"] and not l._is_timeless())
        records.write({"state": "verify"})
        if not records:
            raise UserError(_("This option only could be used in draft/verify loans and with a positive payment term"))

        for loan in self.filtered(lambda l: l.state in ["draft", "verify"] and not l._is_timeless()):
            vals_list = []
            days = loan.employee_id.contract_id.hr_schedule_payment_id.days_to_pay or 0
            for num in range(loan.payment_term):
                sequence = num + 1
                vals_list.append(
                    {
                        "sequence": sequence,
                        "loan_id": loan.id,
                        "name": "%s (%d)" % (loan.name, sequence),
                        "date": loan.date_from + relativedelta(days=days * num) if days else loan.date_from,
                        "amount": loan.amount,
                    }
                )
            loan.write(
                {
                    "loan_line_ids": [Command.create(vals) for vals in vals_list],
                }
            )
            loan.loan_line_ids._compute_cumulative_and_remaining_amount()

    def action_get_payslips_view(self):
        return {
            "name": _("Loan Payslips"),
            "view_type": "form",
            "view_mode": "list,form",
            "res_model": "hr.payslip",
            "view_id": False,
            "type": "ir.actions.act_window",
            "domain": [("id", "in", self.payslip_ids.filtered(lambda rec: rec.state == "done").ids)],
        }

    def _is_timeless(self):
        """This method allows to know if the loan is going to be paid indefinitely.
        It is specially important to know if the the table will be created or not.
        The idea of this method is to be consumed by other methods, and make the code
        easier to read and inherit
        """
        self.ensure_one()
        return self.payment_term <= -1

    def action_recompute_sheet(self):
        """After the loan is set running, there are some reasons that can change the amount in the loan lines, what
        happens if the loan is not longer valid, the main idea is that the user will review and reconfirm the loan
        manually, however this method will allow to rebuild automatically the loan considering the amount that
        are already deducted to help the user to adjust the loan.
        """
        for loan in self.filtered(lambda l: not l._is_timeless()):
            if loan.loan_line_ids and loan.loan_line_ids[-1].remaining_amount == 0:
                continue

            loan.loan_line_ids.filtered(lambda l: not l.payslip_id).unlink()
            vals_list = []
            sequence = len(loan.loan_line_ids) + 1
            days = loan.employee_id.contract_id.hr_schedule_payment_id.days_to_pay or 0
            remaining = loan.total_amount - sum(loan.mapped("loan_line_ids.amount"))
            while remaining > 0:
                amount = loan.amount if remaining > loan.amount else remaining
                vals_list.append(
                    {
                        "sequence": sequence,
                        "loan_id": loan.id,
                        "name": "%s (%d)" % (loan.name, sequence),
                        "date": loan.date_from + relativedelta(days=days * (sequence - 1)) if days else loan.date_from,
                        "amount": amount,
                    }
                )
                remaining -= amount
                sequence += 1
            loan.write(
                {
                    "loan_line_ids": [Command.create(vals) for vals in vals_list],
                }
            )

    def action_confirm(self):
        timeless = self.filtered(lambda r: r._is_timeless())
        timeless.write({"state": "active"})
        for record in self - timeless:
            if not record.employee_id:
                raise ValidationError(_("Define an employee to allow confirm"))
            if not record.amount:
                raise ValidationError(_("The amount is required to continue."))
            if not record.input_type_id:
                raise ValidationError(_("An input type is required to continue."))
            record.check_table_integrity()
            record.write({"state": "active", "error_message": False})

    def action_force_confirm(self):
        if not self.env.user.has_group("hr_payroll_loan.allow_force_validate_loan"):
            raise UserError(_("Only Managers who are allow to force validate loans can perform this operation"))
        loans = self.filtered(lambda l: l.state in ["unlocked", "verify"])
        loans.write({"state": "active"})

    def action_close(self):
        self.write({"state": "close", "error_message": False})

    def action_unlocked(self):
        self.write({"state": "unlocked"})

    def _inverse_total_amount(self):
        for record in self:
            if record._is_timeless():
                record.amount = 0
                continue
            record.amount = record.total_amount / (record.payment_term or 1)

    def get_next_line(self):
        """This method will get the next loan line to be considered in the payslip, the next line should must not have
        a payslip linked and, to make sure the line is the correct one, they are sorted by sequence. Get the next
        line getting the first line in the list filtered and sorted.
        """
        self.ensure_one()
        if not self.loan_line_ids:
            return self.browse()
        return self.loan_line_ids.filtered(lambda l: not l.payslip_id.id).sorted(key=lambda l: l.sequence)[0]

    def assign_payslip(self, payslip):
        """This method will assign a payslip to the loan, updating the loan lines with a new payment."""
        for input_type in self.mapped("input_type_id"):
            # Inputs are created with rule code but in lower and with a _ to split the code and number, ex: d_001
            input_code = input_type.code.upper().replace("_", "")
            payslip_line = payslip.line_ids.filtered(lambda l: l.amount and l.code == input_code)
            if not payslip_line:
                continue

            payslip_amount = abs(payslip_line.total)
            loans = self.filtered(lambda l: l.input_type_id == input_type)
            for loan in loans:
                if payslip_amount <= 0:
                    continue
                line_amount = loan.amount
                # If the loan is the last one or the payslip amount is less than the loan amount,
                # the amount will be the remaining amount.
                if loan == loans[-1] or payslip_amount <= loan.amount:
                    line_amount = payslip_amount
                # Update the payslip amount to be used in the next loan.
                payslip_amount -= line_amount
                # Create the loan line with the amount calculated.
                if loan._is_timeless():
                    self.create_loan_line_timeless(payslip, payslip_line, loan, line_amount)
                    continue

                loan_line = loan.get_next_line()
                if loan_line:
                    self.create_loan_line_fixed(payslip, payslip_line, loan, line_amount, loan_line)

    def create_loan_line_timeless(self, payslip, payslip_line, loan, line_amount):
        last_line = loan.loan_line_ids.sorted(key=lambda l: l.sequence)[-1] if loan.loan_line_ids else False
        vals = {
            "payslip_line_id": payslip_line.id,
            "sequence": last_line.sequence + 1 if last_line else 1,
            "loan_id": loan.id,
            "date": payslip.date_from,
            "name": "%s (%d)" % (loan.name, last_line.sequence + 1 if last_line else 1),
            "amount": line_amount,
            "cumulative_amount": payslip_line.total + (last_line.cumulative_amount if last_line else 0),
            "remaining_amount": 0.0,
        }
        loan.write({"payslip_ids": [Command.link(payslip.id)], "loan_line_ids": [Command.create(vals)]})

    def create_loan_line_fixed(self, payslip, payslip_line, loan, line_amount, loan_line):
        loan_line.write(
            {
                "payslip_line_id": payslip_line.id,
                "date": payslip.date_from,
                "amount": line_amount,
            }
        )
        loan.write({"payslip_ids": [Command.link(payslip.id)]})
        loan.loan_line_ids._compute_cumulative_and_remaining_amount()
        loan._loan_done_check()

    def _loan_done_check(self):
        """This method will check if the loan is complete or not, also check if the loan is still valid.
        After a payslip validation and after link the payslip to the loan, check if the loan is complete, if so,
        Set the loan as close / done.
        If the loan is not complete and the next loan line is the last line, check if the loan will be
        correctly finished, if not, set the loan as unlocked and ask for user intervation."""
        self.ensure_one()
        if not self.loan_line_ids.filtered(lambda l: not l.payslip_id) or self.payslips_count >= self.payment_term > 0:
            self.write({"state": "close"})
            return
        next_line = self.get_next_line()
        if next_line and next_line == self.loan_line_ids[-1] and next_line.remaining_amount:
            self.write(
                {
                    "state": "unlocked",
                    "error_message": _(
                        "The following loan lines will get a negative remaining amount, please review "
                        "the loan amounts and make the necessary adjustments."
                    ),
                }
            )
            self.activity_schedule(
                "mail.mail_activity_data_todo", note=_("Review the loan amounts"), user_id=self.env.user.id
            )

    def check_table_integrity(self):
        """Check if the loan table is correctly filled out, and it is valid to set running the loan"""
        self.ensure_one()
        if self._is_timeless():
            return False
        if not self.loan_line_ids:
            raise ValidationError(_("The amortization table is empty, it can not be validated"))
        if self.loan_line_ids[-1].remaining_amount:
            raise ValidationError(
                _(
                    "The loan is not fully paid or has excess payments, "
                    "please review the table and make the necessary adjustments."
                )
            )
