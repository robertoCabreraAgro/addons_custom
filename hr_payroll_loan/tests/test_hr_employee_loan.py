import time

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestEmployeeLoan(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.payslip_obj = cls.env["hr.payslip"]
        cls.employee = cls.env.ref("hr.employee_qdp")
        cls.contract = cls.env.ref("hr_payroll.hr_contract_gilles_gravie")
        cls.contract.state = "open"
        cls.struct_id = cls.env.ref("hr_payroll.structure_worker_001")
        cls.loan_id = cls.env.ref("hr_payroll_loan.life_ensurance_demo")
        cls.prepare_account_settings()

    @classmethod
    def prepare_account_settings(cls):
        """Method to set accounting settings for payroll, just if hr_payroll_account is installed.
        Avoid to add accounting to dependencies in this module."""
        if not cls.env["ir.module.module"].search([("name", "=", "hr_payroll_account"), ("state", "=", "installed")]):
            return False
        cls.journal_id = (
            cls.env["account.journal"]
            .sudo()
            .search([("type", "=", "general"), ("company_id", "=", cls.env.company.id)], limit=1)
        )
        cls.journal_id.default_account_id = cls.env["account.account"].create(
            {
                "code": "601.08.01",
                "name": "Payroll Expense",
                "account_type": "expense",
                "company_id": cls.contract.company_id.id,
            }
        )
        cls.struct_id.journal_id = cls.journal_id
        return True

    def create_payroll(self):
        return self.payslip_obj.create(
            {
                "name": "Payslip Test",
                "employee_id": self.employee.id,
                "contract_id": self.contract.id,
                "struct_id": self.struct_id.id,
                "date_from": "%s-%s-01" % (time.strftime("%Y"), time.strftime("%m")),
                "date_to": "%s-%s-15" % (time.strftime("%Y"), time.strftime("%m")),
                "input_line_ids": [
                    Command.clear(),
                    Command.create(
                        {
                            "input_type_id": self.ref("hr_payroll_loan.hr_rule_input_loan_deduction_life_insurance"),
                        }
                    ),
                ],
            }
        )

    def test_001_regular_flow(self):
        """Ensure that loan is working correctly in a regular usage"""
        self.loan_id.action_confirm()
        payroll = self.create_payroll()
        payroll.compute_sheet()
        payroll.action_payslip_done()
        self.assertEqual(self.loan_id.payslips_count, 1, "Payslip not applied in the loan.")
        self.assertEqual(self.employee.loan_count, 1, "Loan not found.")

        loan_line = payroll.line_ids.filtered(lambda l: l.code == "LED" and l.amount)
        self.assertEqual(
            len(loan_line),
            1,
            "There should be a loan line in the payslip",
        )
        self.assertEqual(
            loan_line.amount,
            1800,
            "The line amount must be the same than the amount in the loan",
        )

    def test_002_multi_loan(self):
        """Ensure using more than one loan will work without problems, Also test create new loans (loan and rule)"""
        salary_rule_form = Form(self.env["hr.salary.rule"])
        salary_rule_form.name = "Car Loan"
        salary_rule_form.sequence = "50"
        salary_rule_form.code = "CLD"
        salary_rule_form.category_id = self.env.ref("hr_payroll.DED")
        salary_rule_form.struct_id = self.struct_id
        salary_rule_form.condition_select = "none"
        salary_rule_form.amount_select = "code"
        salary_rule_form.amount_python_compute = "result = sum(payslip.get_loans('cld_01').mapped('amount'))"
        salary_rule_form.save()

        second_loan = self.loan_id.copy()
        payslip_input_type_form = Form(self.env["hr.payslip.input.type"])
        payslip_input_type_form.code = "cld_01"
        payslip_input_type_form.name = "Car Loan"
        payslip_input_type_form.use_in_loan = True
        payslip_input_type_form.struct_ids = self.struct_id
        payslip_input_type = payslip_input_type_form.save()

        second_loan.input_type_id = payslip_input_type
        second_loan.amount = 2500
        third_loan = second_loan.copy()
        self.loan_id.action_confirm()
        second_loan.action_confirm()
        third_loan.action_confirm()

        payroll = self.create_payroll()
        payroll.compute_sheet()
        payroll.action_payslip_done()
        self.assertEqual(self.employee.loan_count, 3, "The employee must have 3 loans")

        loan_line = payroll.line_ids.filtered(lambda l: l.code == "LED" and l.amount)
        self.assertEqual(len(loan_line), 1, "There should be just one loan line in the payslip")
        self.assertEqual(loan_line.amount, 1800, "The line amount must be the same than the amount in the loan")

        loan_car_line = payroll.line_ids.filtered(lambda l: l.code == "CLD" and l.amount)
        self.assertEqual(len(loan_car_line), 1, "There should be just one loan CLD line in the payslip")
        self.assertEqual(
            loan_car_line.amount,
            second_loan.amount + third_loan.amount,
            "The line amount must be %d" % (second_loan.amount + third_loan.amount),
        )

    def test_003_inactive_loans(self):
        """Test the states flow of the loans and test if the loan is being considered in the payslip compute.
        Inactive or finished or not in period Loans should not been called"""
        payment_term = 3
        loan_amount = 1000
        self.loan_id.write(
            {
                "amount": loan_amount,
                "payment_term": payment_term,
            }
        )
        payroll = self.create_payroll()
        # Inactive Loan, at this point the loan is not confirmed and should not be called
        payroll.compute_sheet()
        loan_line = payroll.line_ids.filtered(lambda l: l.code == "LED" and l.amount)
        self.assertFalse(loan_line, "The payslip shouldn't have loan line with amount")
        self.loan_id.compute_sheet()
        self.assertEqual(self.loan_id.state, "verify")
        loan_line = payroll.line_ids.filtered(lambda l: l.code == "LED" and l.amount)
        self.assertFalse(loan_line, "The payslip shouldn't have loan line with amount")
        # Now Confirm
        self.loan_id.action_confirm()
        self.assertEqual(self.loan_id.state, "active")
        payroll.compute_sheet()
        loan_line = payroll.line_ids.filtered(lambda l: l.code == "LED" and l.amount)
        self.assertTrue(loan_line, "The payslip should have loan line with amount")
        # Now set in edition mode
        self.loan_id.action_unlocked()
        self.assertEqual(self.loan_id.state, "unlocked")
        payroll.compute_sheet()
        loan_line = payroll.line_ids.filtered(lambda l: l.code == "LED" and l.amount)
        self.assertFalse(loan_line, "The payslip shouldn't have loan line with amount")
        # Come back to active
        self.loan_id.action_confirm()
        payroll.compute_sheet()
        loan_line = payroll.line_ids.filtered(lambda l: l.code == "LED" and l.amount)
        self.assertTrue(loan_line, "The payslip must have a loan line")
        # Date, period out of payslip period
        month = payroll.date_from.month
        self.loan_id.date_from = payroll.date_from.replace(month=month - 1)
        self.loan_id.date_to = payroll.date_to.replace(month=month - 1)
        payroll.compute_sheet()
        loan_line = payroll.line_ids.filtered(lambda l: l.code == "LED" and l.amount)
        self.assertFalse(loan_line, "There shouldn't be any loan line in the payslip")

    def test_004_loan_count(self):
        self.loan_id.action_confirm()
        payroll = self.create_payroll()
        payroll.compute_sheet()
        payroll.action_payslip_done()
        self.assertEqual(self.loan_id.payslips_count, 1, "Payslip not applied in the loan.")

        payroll2 = self.create_payroll()
        payroll2.compute_sheet()
        payroll2.action_payslip_done()
        self.assertEqual(self.loan_id.payslips_count, 2, "Payslip not applied in the loan.")

        # Force state and check if a cancelled payslip affects count
        payroll.action_payslip_cancel()
        self.assertEqual(self.loan_id.payslips_count, 1, "Loan should have just 1 Payslip.")

    def test_005_timeless_loan(self):
        """Test when the loan is a timeless or with a period undefined.
        The table should not be created, The important thing here is that the payslip should get the amount of the
        loan directly and when the payslips are confirmed, the line should be created.
        """
        loan_amount = 1500.00
        self.loan_id.write(
            {
                "amount": loan_amount,
                "payment_term": -1,
            }
        )
        self.assertEqual(self.loan_id.state, "draft")
        self.assertFalse(self.loan_id.loan_line_ids, "This option should not generate table")
        self.loan_id.action_confirm()
        self.assertEqual(self.loan_id.state, "active")
        payroll = self.create_payroll()
        payroll.compute_sheet()
        payslip_loan_line = payroll.line_ids.filtered(lambda l: l.code == "LED")
        self.assertEqual(payslip_loan_line.total, loan_amount)
        payroll.action_payslip_done()
        self.assertEqual(len(self.loan_id.loan_line_ids), 1, "Now there should be just one line in the loan")
        loan_line = self.loan_id.loan_line_ids
        self.assertEqual(loan_line.amount, loan_amount)
        self.assertEqual(loan_line.cumulative_amount, loan_amount)
        self.assertEqual(loan_line.remaining_amount, 0)
        # Second Payslip
        payroll = self.create_payroll()
        payroll.compute_sheet()
        payslip_loan_line = payroll.line_ids.filtered(lambda l: l.code == "LED")
        self.assertEqual(payslip_loan_line.total, loan_amount)
        payroll.action_payslip_done()
        self.assertEqual(len(self.loan_id.loan_line_ids), 2, "Now there should two lines in the loan")
        loan_line = self.loan_id.loan_line_ids[-1]
        self.assertEqual(loan_line.amount, loan_amount)
        self.assertEqual(loan_line.cumulative_amount, loan_amount * 2)
        self.assertEqual(loan_line.remaining_amount, 0)
        # Third Payslip, changing for any reason the amount but in the payslip
        payroll = self.create_payroll()
        payroll.compute_sheet()
        payslip_loan_line = payroll.line_ids.filtered(lambda l: l.code == "LED")
        payslip_loan_line.write({"amount": loan_amount + 500, "total": loan_amount + 500})
        payroll.action_payslip_done()
        self.assertEqual(len(self.loan_id.loan_line_ids), 3, "Now there should be three lines in the loan")
        loan_line = self.loan_id.loan_line_ids[-1]
        self.assertEqual(
            loan_line.amount,
            payslip_loan_line.total,
            "The amount in the new loan line should be consistent with the amount in the payslip line",
        )
        self.assertEqual(loan_line.cumulative_amount, (loan_amount * 3 + 500))
        self.assertEqual(loan_line.remaining_amount, 0)

    def test_006_table_defined_period(self):
        """Test the table generation when the loan has a limited times to be paid (payment term)"""
        payment_term = 12
        loan_amount = 1000
        self.loan_id.write(
            {
                "amount": loan_amount,
                "payment_term": payment_term,
            }
        )
        self.loan_id.compute_sheet()
        self.assertEqual(self.loan_id.state, "verify")
        self.assertTrue(self.loan_id.loan_line_ids, "This option must generate the table")
        self.loan_id.action_confirm()

        # Table check
        self.assertEqual(len(self.loan_id.loan_line_ids), payment_term, "The table should be the same as the term")
        lines = self.loan_id.loan_line_ids.filtered(lambda l: l.amount != loan_amount)
        self.assertFalse(lines, "All lines should have the same amount")
        self.assertEqual(self.loan_id.total_amount, loan_amount * payment_term, "The loan total amount is incorrect")
        # Amount check
        first_line = self.loan_id.loan_line_ids[0]
        self.assertEqual(first_line.amount, loan_amount, "The amount expected is the loan amount")
        self.assertEqual(first_line.cumulative_amount, loan_amount)
        self.assertEqual(first_line.remaining_amount, loan_amount * (payment_term - 1))
        last_line = self.loan_id.loan_line_ids[-1]
        self.assertEqual(last_line.amount, loan_amount, "The amount expected is the loan amount")
        self.assertEqual(last_line.cumulative_amount, loan_amount * payment_term)
        self.assertEqual(last_line.remaining_amount, 0)
        # Create payroll
        payroll = self.create_payroll()
        payroll.compute_sheet()
        payslip_loan_line = payroll.line_ids.filtered(lambda l: l.code == "LED")
        self.assertEqual(payslip_loan_line.total, loan_amount)
        payroll.action_payslip_done()
        # Now check the loan after the payslip confirm
        loan_line = self.loan_id.loan_line_ids.filtered("payslip_id")
        self.assertEqual(len(loan_line), 1, "There must be one line with a payslip linked")
        self.assertEqual(loan_line, first_line, "The payslip should be assigned to the first loan line")
        self.assertEqual(loan_line.amount, loan_amount)
        self.assertEqual(loan_line.cumulative_amount, loan_amount)
        self.assertEqual(loan_line.remaining_amount, loan_amount * (payment_term - 1))
        # Second Payslip
        payroll = self.create_payroll()
        payroll.compute_sheet()
        payslip_loan_line = payroll.line_ids.filtered(lambda l: l.code == "LED")
        self.assertEqual(payslip_loan_line.total, loan_amount)
        payroll.action_payslip_done()
        loan_line = self.loan_id.loan_line_ids.filtered("payslip_id")
        self.assertEqual(len(loan_line), 2, "Now there must be two lines in the loan with a payslip linked")
        loan_line = loan_line[-1]
        self.assertEqual(loan_line.amount, loan_amount)
        self.assertEqual(loan_line.cumulative_amount, loan_amount * 2)
        self.assertEqual(loan_line.remaining_amount, loan_amount * (payment_term - 2))
        # Third Payslip, changing for any reason the amount but in the payslip
        payroll = self.create_payroll()
        payroll.compute_sheet()
        payslip_loan_line = payroll.line_ids.filtered(lambda l: l.code == "LED")
        payslip_loan_line.write({"amount": loan_amount + 500, "total": loan_amount + 500})
        payroll.action_payslip_done()
        loan_line = self.loan_id.loan_line_ids.filtered("payslip_id")
        self.assertEqual(len(loan_line), 3, "Now there should be three lines in the loan")
        loan_line = loan_line[-1]
        self.assertEqual(
            loan_line.amount,
            payslip_loan_line.total,
            "The amount in the new loan line should be consistent with the amount in the payslip line",
        )
        self.assertEqual(loan_line.cumulative_amount, (loan_amount * 3 + 500))
        self.assertEqual(loan_line.remaining_amount, loan_amount * (payment_term - 3) - 500)

    def test_007_check_total_amount_inverse(self):
        """Test that if we set the total amount instead the amount, the regular amount will be changed automacally"""
        self.loan_id.write(
            {
                "total_amount": 12000,
                "payment_term": 12,
            }
        )
        self.assertEqual(self.loan_id.amount, 1000, "The expected amount is 1000 (total_amount / payment_term)")

    def test_008_block_validation_no_valid_loan(self):
        """Check if the validation of a loan is being perform before confirm it again"""
        payment_term = 12
        loan_amount = 1000

        self.loan_id.write(
            {
                "amount": loan_amount,
                "payment_term": payment_term,
            }
        )
        self.loan_id.compute_sheet()
        self.assertEqual(self.loan_id.state, "verify")
        self.assertTrue(self.loan_id.loan_line_ids, "This option must generate the table")
        self.loan_id.action_confirm()

        # Create payroll
        payroll = self.create_payroll()
        payroll.compute_sheet()
        payroll.action_payslip_done()
        # Second Payslip, changing for any reason the amount but in the payslip
        payroll = self.create_payroll()
        payroll.compute_sheet()
        payslip_loan_line = payroll.line_ids.filtered(lambda l: l.code == "LED")
        payslip_loan_line.write({"amount": loan_amount + 500, "total": loan_amount + 500})
        payroll.action_payslip_done()

        self.loan_id.action_unlocked()
        with self.assertRaises(
            UserError,
            msg="The loan is not fully paid or has excess payments, "
            "please review the table and make the necessary adjustments.",
        ):
            self.loan_id.action_confirm()
        self.loan_id.action_recompute_sheet()
        self.loan_id.action_confirm()
        self.assertEqual(self.loan_id.state, "active")
        self.assertTrue(
            self.loan_id.loan_line_ids.filtered("payslip_id"),
            "There should be a line with payslop, maybe the line was deleted",
        )
        self.assertEqual(
            self.loan_id.loan_line_ids[-1].remaining_amount,
            0,
            "After recompute the sheet, the remaning amount in the last line should be 0",
        )

    def test_009_allow_validate_invalid_loan(self):
        """Test case when the uses try to force an invalid loan, just an authorized user can do it"""
        self.loan_id.write(
            {
                "payment_term": 3,
            }
        )
        self.loan_id.compute_sheet()
        self.assertEqual(self.loan_id.state, "verify")
        self.assertTrue(self.loan_id.loan_line_ids, "This option must generate the table")
        self.loan_id.action_confirm()
        self.loan_id.action_unlocked()
        with self.assertRaises(
            UserError, msg="Only Managers who are allow to force validate loans can perform this operation"
        ):
            self.loan_id.action_force_confirm()
        # Give permissions and try again to finish the test
        group_e = self.env.ref("hr_payroll_loan.allow_force_validate_loan", False)
        group_e.sudo().write({"users": [Command.link(self.env.user.id)]})
        self.loan_id.action_force_confirm()

    def test_010_no_link_not_applied_loan(self):
        self.loan_id.write(
            {
                "amount": 1000,
                "payment_term": 3,
            }
        )
        self.loan_id.compute_sheet()
        self.loan_id.action_confirm()
        # For any reason the loan were not apply on payslip, maybe was not time to be paid
        payroll = self.create_payroll()
        payroll.compute_sheet()
        payslip_loan_line = payroll.line_ids.filtered(lambda l: l.code == "LED")
        self.assertTrue(payslip_loan_line, "Payslip Line off the loan were not found")
        # Force value as 0, but could be 0 for more reasons
        payslip_loan_line.write({"amount": 0, "total": 0})
        payroll.action_payslip_done()
        loan_line = self.loan_id.loan_line_ids.filtered("payslip_id")
        self.assertFalse(loan_line, "The payslip should not be linked to the loan, the amount in the payslip is 0")

    def test_011_multi_loan_fixed_term_values(self):
        """Test the values of the loan lines when the loan has a fixed term"""
        self.loan_id.amount = 1000
        self.loan_id.payment_term = 5

        loans = self.loan_id | self.loan_id.copy()
        loans.compute_sheet()
        loans.action_confirm()
        payroll = self.create_payroll()
        payroll.compute_sheet()
        payroll.action_payslip_done()

        for rec in loans:
            self.assertEqual(rec.payslips_count, 1, "Payslip not applied in loan.")
            self.assertEqual(rec.total_amount, 5000, "The total amount is incorrect.")
            self.assertEqual(rec.amount_paid, 1000, "The amount paid is incorrect.")
            self.assertEqual(rec.amount_remaining, 4000, "The remaining amount is incorrect.")
            line = rec.loan_line_ids[0]
            self.assertEqual(line.amount, rec.amount, "The amount is incorrect on the first line is incorrect.")
            self.assertEqual(
                line.cumulative_amount, rec.amount, "The cumulative amount on the first line is incorrect."
            )
            self.assertEqual(
                line.remaining_amount,
                rec.total_amount - rec.amount,
                "The remaining amount on the first line is incorrect.",
            )
            line = rec.loan_line_ids[-1]
            self.assertEqual(line.amount, rec.amount, "The amount is incorrect on the last line is incorrect.")
            self.assertEqual(
                line.cumulative_amount, rec.total_amount, "The cumulative amount on the last line is incorrect."
            )
            self.assertEqual(line.remaining_amount, 0, "The remaining amount on the last line is incorrect.")
