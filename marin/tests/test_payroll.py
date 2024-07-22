from datetime import datetime, timedelta

from odoo.exceptions import UserError
from odoo.tests.common import Form, tagged

from odoo.addons.l10n_mx_edi_payslip.tests.common import L10nMxEdiPayslipTransactionCase


@tagged("hr_payroll", "post_install", "-at_install")
class TestHRPayroll(L10nMxEdiPayslipTransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.date = datetime.today() + timedelta(days=5)
        cls.payslip_run = cls.env["hr.payslip.run"].create(
            {
                "name": "Payslip VX",
                "date_end": cls.date,
            }
        )
        cls.env.ref("l10n_mx_edi_payslip.mx_employee_qdp").work_contact_id = cls.env.ref(
            "l10n_mx_edi_payslip.res_partner_address_mx_qdp"
        )

    def test_01_payroll_l10n_mx_edi_is_required(self):
        payroll = self.create_payroll()
        journal = payroll.struct_id.journal_id.sudo()
        self.assertFalse(payroll.l10n_mx_edi_is_required())
        journal.x_treatment = "fiscal_real"
        self.assertTrue(payroll.l10n_mx_edi_is_required())
        journal.x_treatment = "not_fiscal_simulated"
        self.assertFalse(payroll.l10n_mx_edi_is_required())
        journal.x_treatment = "fiscal_simulated"
        self.assertTrue(payroll.l10n_mx_edi_is_required())

    def test_02_payroll_onchange_contract(self):
        default_struct = self.struct
        self.struct = self.env.ref("l10n_mx_edi_payslip.payroll_structure_data_06")
        payroll = self.create_payroll()
        self.assertEqual(payroll.struct_id, self.struct)
        self.assertTrue(payroll.struct_id != default_struct)
        contract = payroll.contract_id
        contract2 = self.env.ref("l10n_mx_edi_payslip.hr_contract_felix")
        self.assertTrue(contract != contract2)
        self.assertEqual(contract.structure_type_id.default_struct_id, default_struct)
        self.assertEqual(contract2.structure_type_id.default_struct_id, default_struct)
        # Verify that compute method doesn't change the struct when changing the contract
        # and payroll already has a struct
        payroll.contract_id = contract2
        self.assertEqual(payroll.struct_id, self.struct)
        self.assertTrue(payroll.struct_id != default_struct)
        payroll.contract_id = contract
        self.assertEqual(payroll.struct_id, self.struct)
        self.assertTrue(payroll.struct_id != default_struct)
        # Verify that onchange method will change the struct when changing the contract
        # even if the payroll already has a struct
        with Form(payroll) as form_payroll:
            form_payroll.contract_id = contract2
        form_payroll.save()
        self.assertEqual(payroll.struct_id, default_struct)

    def test_03_payroll_edi_number_of_days(self):
        payroll = self.create_payroll()
        payroll.compute_sheet()
        payroll.action_payslip_done()
        values = payroll._l10n_mx_edi_create_cfdi_values()
        self.assertEqual(sum(payroll.worked_days_line_ids.mapped("number_of_days")), values["number_of_days"])

    def test_04_payroll_run_create_moves(self):
        payroll = self.create_payroll()
        payroll.compute_sheet()
        payroll.payslip_run_id = self.payslip_run
        self.payslip_run.create_payslip_moves()

    def test_05_payroll_action_payslip_move_post(self):
        payroll = self.create_payroll()
        payroll.compute_sheet()
        self.env.user.groups_id = [(3, self.env.ref("l10n_mx_edi_payslip.allow_validate_payslip").id)]
        with self.assertRaisesRegex(
            UserError, "Only Managers who are allow to validate payslip can perform this operation"
        ):
            payroll.action_payslip_move_post()
        self.env.user.groups_id = [(4, self.env.ref("l10n_mx_edi_payslip.allow_validate_payslip").id)]
        with self.assertRaisesRegex(UserError, "Cannot post a payslip's account move that is not done."):
            payroll.action_payslip_move_post()
        self.assertFalse(payroll.move_id)
        payroll.action_payslip_done()
        self.assertTrue(payroll.move_id)
        self.assertEqual(payroll.move_id.state, "draft")
        payroll.action_payslip_move_post()
        self.assertEqual(payroll.move_id.state, "posted")
