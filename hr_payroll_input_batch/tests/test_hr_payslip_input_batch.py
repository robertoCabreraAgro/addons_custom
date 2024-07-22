import time

from odoo import Command
from odoo.tests import Form, TransactionCase, tagged


@tagged("hr_payslip_input_batch")
class TestHrPayslipInputBatch(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env.ref("hr.employee_qdp")
        cls.contract = cls.env.ref("hr_payroll.hr_contract_gilles_gravie")
        cls.contract.state = "open"
        cls.struct_id = cls.env.ref("hr_payroll.structure_002")
        cls.input = cls.env["hr.payslip.input.type"].create(
            {"code": "T01", "name": "Test 01", "struct_ids": [Command.set(cls.struct_id.ids)]}
        )

    def create_payroll(self):
        return self.env["hr.payslip"].create(
            {
                "name": "Payslip Test",
                "employee_id": self.employee.id,
                "contract_id": self.contract.id,
                "struct_id": self.struct_id.id,
                "date_from": "%s-%s-01" % (time.strftime("%Y"), time.strftime("%m")),
                "date_to": "%s-%s-15" % (time.strftime("%Y"), time.strftime("%m")),
            }
        )

    def test_001_inputs(self):
        """Ensure that input batch is added on the payroll"""
        payroll = self.create_payroll()
        # Prepare batch
        input_batch_form = Form(self.env["hr.payslip.input.batch"])
        input_batch_form.name = "Input T01"
        input_batch_form.input_id = self.input
        input_batch_form.date = payroll.date_from
        with input_batch_form.detail_ids.new() as line1:
            line1.employee_id = self.employee
            line1.amount = 120
        input_batch = input_batch_form.save()
        input_batch.action_approve()
        input_batch.action_open_lines()
        input_batch.action_cancel()
        input_batch.action_approve()

        payroll.update_inputs_from_batch()
        self.assertEqual(
            payroll.input_line_ids.filtered(lambda l: l.input_type_id == self.input).amount,
            120.0,
            "The input amount must be 120.00.",
        )
