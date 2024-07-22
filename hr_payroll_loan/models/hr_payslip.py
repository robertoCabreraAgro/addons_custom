from odoo import Command, models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def action_payslip_done(self):
        """Add the payslip confirmed to the loan to have. Method Splitted with inherence proposes"""
        result = super().action_payslip_done()
        for record in self:
            record._add_payslip_to_loans()
        return result

    def action_payslip_cancel(self):
        """Delete the relationship of the loan and the payslip, just call _cancel_payslip_loan to
        make easier the inherit this behavior.
        """
        res = super().action_payslip_cancel()
        self._cancel_payslip_loan()
        return res

    def _add_payslip_to_loans(self):
        """Add Payslip to loans when the payslip is validated. Method splitted with inherence proposes"""
        self.ensure_one()
        loans = self.get_loans("all") - self._get_to_not_link_loans()
        loans.assign_payslip(self)

    def _cancel_payslip_loan(self):
        """Delete the relationship of the loan and the payslip"""
        for record in self:
            loans = record.get_loans("all", ["active", "close"]) - record._get_to_not_link_loans()
            loans = loans.filtered(lambda loan: record in loan.payslip_ids)
            loans.write({"payslip_ids": [Command.unlink(record.id)]})
            loan_lines = loans.mapped("loan_line_ids").filtered(lambda l: l.payslip_id == record)
            for line in loan_lines:
                loan = line.loan_id
                line.write(
                    {
                        "payslip_line_id": False,
                        "amount": loan.amount,
                    }
                )

    def _get_to_not_link_loans(self):
        """Indicates Which loans are not going to be linked to the payslip. Manage that logic in each localization
        :returns: Loans Salary Rules
        """
        # TO OVERRIDE
        self.ensure_one()
        return self.env["hr.employee.loan"]

    def get_loans(self, input_code, states=None):
        """Get valid loans of a employee between dates.
        A loan is valid if is confirmed and received dates are between loan's dates
        If a loan is confirmed and its dates are not defined, the loan is considered as valid
        """
        # TODO: Check what happened if a loan gets more lines than the payment term, this will not allow to continue
        # with the loan
        date_from = self.date_from
        date_to = self.date_to

        if not states:
            states = ["active"]
        if isinstance(states, str):
            states = [states]

        if input_code == "all":
            # Return all loan types
            return self.employee_id.loan_ids.filtered(
                lambda l: (self.struct_id in l.input_type_id.struct_ids)
                and (l.state in states)
                and (l.payment_term == -1 or l.payslips_count < l.payment_term)
                and (not l.date_from or l.date_from <= date_to)
                and (not l.date_to or l.date_to >= date_to or (l.date_to >= date_from and l.date_to <= date_to))
            )

        loans = self.employee_id.loan_ids.filtered(
            lambda l: l.input_type_id.code == input_code
            and (l.state in states)
            and (self.struct_id in l.input_type_id.struct_ids)
            and (l.payment_term == -1 or l.payslips_count < l.payment_term)
            and (not l.date_from or l.date_from <= date_to)
            and (not l.date_to or l.date_to >= date_to or (l.date_to >= date_from and l.date_to <= date_to))
        )
        return loans

    def _get_loan_breakdown_lines(self):
        self.ensure_one()
        valid_loans = self.get_loans("all", ["active", "close"]).filtered(lambda l: not l._is_timeless())
        return valid_loans.mapped("loan_line_ids").filtered(lambda l: l.payslip_id == self)
