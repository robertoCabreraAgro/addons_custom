import odoo.tests

from odoo.addons.hr_payroll_account.tests.test_hr_payroll_account import (
    TestHrPayrollAccountCommon,
)


@odoo.tests.tagged("post_install", "-at_install")
class TestHrPayrollAccountGlobalEntry(TestHrPayrollAccountCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_01_hr_payslip_global_entry(self):
        """Checking the process with a company marked as non global entry."""
        # Mark company as non global entry.
        self.env.user.company_id.not_global_entry = True

        # Create an account for the HRA salary rule
        self.test_account = self.env["account.account"].create(
            {
                "name": "House Rental",
                "code": "654321",
                "account_type": "income",
            }
        )

        # Assign the account to the salary rule and the rule to the hr structure
        self.hra_rule.account_credit = self.test_account
        self.hra_rule.account_debit = self.test_account
        self.hr_structure_softwaredeveloper.rule_ids = [(4, self.hra_rule.id)]

        # Validate the payslip
        self.hr_payslip_john.compute_sheet()
        self.hr_payslip_john.action_payslip_done()

        slip_moves = self.hr_payslip_john.payslip_run_id.slip_ids.mapped("move_id")
        self.assertEqual(
            len(slip_moves),
            len(self.hr_payslip_john.payslip_run_id.slip_ids),
            "Mismatch between payslips and entries!",
        )
