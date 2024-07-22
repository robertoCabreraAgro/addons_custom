from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    def create_payslip_moves(self):
        """Prepare the creation of journal entries (account.move) by creating a list of python dictionary to be passed
        to the "create" method.
        :return: A list of Python dictionary to be passed to env["account.move"].create.
        """
        precision = self.env["decimal.precision"].precision_get("Payroll")
        for payslip in self.slip_ids:
            partner = payslip.employee_id.user_partner_id
            journal = payslip.struct_id.journal_id
            date = payslip.date
            debit_sum = 0.0
            credit_sum = 0.0
            move_dict = {
                "partner_id": partner.id,
                "journal_id": journal.id,
                "currency_id": journal.currency_id.id or payslip.company_id.currency_id.id,
                "date": date,
                "narration": "",
                "ref": "",
                "line_ids": [],
            }

            for line in payslip.line_ids:
                amount = -line.total if payslip.credit_note else line.total
                if line.code == "NET":  # Check if the line is the "Net Salary".
                    for tmp_line in payslip.line_ids.filtered(lambda tmp: tmp.salary_rule_id.not_computed_in_net):
                        # Check if the rule must be computed in the "Net Salary" or not.
                        amount += abs(tmp_line.total) if amount < 0 else -abs(tmp_line.total) if amount > 0 else 0.0
                if float_is_zero(amount, precision_digits=precision):
                    continue

                debit_account_id = line.salary_rule_id.account_debit.id
                credit_account_id = line.salary_rule_id.account_credit.id

                if debit_account_id:  # If the rule has a debit account.
                    debit = amount if amount > 0.0 else 0.0
                    credit = -amount if amount < 0.0 else 0.0
                    debit_line = {
                        "name": line.name,
                        "partner_id": partner.id,
                        "account_id": debit_account_id,
                        "journal_id": journal.id,
                        "date": date,
                        "debit": debit,
                        "credit": credit,
                        "analytic_account_id": line.salary_rule_id.analytic_account_id.id
                        or payslip.contract_id.analytic_account_id.id,
                    }
                    move_dict["line_ids"].append((0, 0, debit_line))
                    debit_sum += debit
                    credit_sum += credit

                if credit_account_id:  # If the rule has a credit account.
                    debit = -amount if amount < 0.0 else 0.0
                    credit = amount if amount > 0.0 else 0.0
                    credit_line = {
                        "name": line.name,
                        "partner_id": partner.id,
                        "account_id": credit_account_id,
                        "journal_id": journal.id,
                        "date": date,
                        "debit": debit,
                        "credit": credit,
                        "analytic_account_id": line.salary_rule_id.analytic_account_id.id
                        or payslip.contract_id.analytic_account_id.id,
                    }
                    move_dict["line_ids"].append((0, 0, credit_line))
                    debit_sum += debit
                    credit_sum += credit

            if float_compare(credit_sum, debit_sum, precision_digits=precision) == -1:
                acc_id = journal.default_credit_account_id
                if not acc_id:
                    raise UserError(
                        _('The Expense Journal "%s" has not properly configured the Credit Account!', journal.name)
                    )
                adjust_credit = {
                    "name": _("Adjustment Entry"),
                    "partner_id": partner.id,
                    "account_id": acc_id.id,
                    "journal_id": journal.id,
                    "date": date,
                    "debit": 0.0,
                    "credit": debit_sum - credit_sum,
                }
                move_dict["line_ids"].append((0, 0, adjust_credit))

            elif float_compare(debit_sum, credit_sum, precision_digits=precision) == -1:
                acc_id = journal.default_debit_account_id
                if not acc_id:
                    raise UserError(
                        _('The Expense Journal "%s" has not properly configured the Debit Account!', journal.name)
                    )
                adjust_debit = {
                    "name": _("Adjustment Entry"),
                    "partner_id": partner.id,
                    "account_id": acc_id.id,
                    "journal_id": journal.id,
                    "date": date,
                    "debit": credit_sum - debit_sum,
                    "credit": 0.0,
                }
                move_dict["line_ids"].append((0, 0, adjust_debit))

        return move_dict
