import time
from datetime import datetime, timedelta

from odoo import Command
from odoo.tests.common import TransactionCase


class TestPayrollDispersion(TransactionCase):
    def setUp(self):
        super().setUp()
        self.employee = self.env.ref("hr.employee_qdp")
        self.contract = self.env.ref("hr_payroll.hr_contract_gilles_gravie")
        self.struct = self.env.ref("hr_payroll.structure_002")
        self.date = datetime.today() + timedelta(days=5)
        self.payslip_run = self.env["hr.payslip.run"].create(
            {
                "name": "Payslip VX",
                "date_end": self.date,
            }
        )
        self.dispersion_group = self.env.ref("hr_bank_dispersion.allow_print_payslip_dispersion", False)
        self.dispersion_group.sudo().write({"users": [Command.set([self.env.user.id, 1])]})

    def test_001_payslip_dispersion(self):
        self.employee.bank_account_id = self.employee.bank_account_id.create(
            {
                "acc_number": "1234567890",
                "bank_id": self.ref("base.bank_ing"),
                "partner_id": self.ref("base.partner_demo"),
            }
        )
        report_name = self.payslip_run._get_payslips_dispersion_report_name("BBVA BANCOMER")
        self.assertEqual(
            report_name,
            "BBVA_BANCOMER_%s_Payslip_VX" % self.date.strftime("%d_%m_%Y"),
            "Wrong payslip dispersion file name",
        )

        payroll = self.create_payroll()
        payroll.compute_sheet()
        payroll.payslip_run_id = self.payslip_run

        dispersion_text = self.payslip_run._get_payslips_dispersions()[0][1]
        # Preparing amount
        amount = payroll.net_wage
        amount = str(amount).replace(".", "").zfill(15)
        self.assertEqual(
            dispersion_text,
            "000000001                991234567890          %s"
            "Marc Demo                               001001\r\n" % amount,
            "Wrong payslip dispersion template",
        )

    def create_payroll(self, date_from=None, date_to=None):
        return self.env["hr.payslip"].create(
            {
                "name": "Payslip Test",
                "employee_id": self.ref("hr.employee_qdp"),
                "contract_id": self.ref("hr_payroll.hr_contract_gilles_gravie"),
                "struct_id": self.ref("hr_payroll.structure_002"),
                "date_from": date_from or "%s-%s-01" % (time.strftime("%Y"), time.strftime("%m")),
                "date_to": date_to or "%s-%s-15" % (time.strftime("%Y"), time.strftime("%m")),
                "worked_days_line_ids": [
                    Command.create(
                        {
                            "name": "Normal Working Days",
                            "code": "WORK100",
                            "number_of_days": 15,
                            "number_of_hours": 40,
                            "contract_id": self.contract.id,
                            "work_entry_type_id": self.ref("hr_work_entry.work_entry_type_attendance"),
                        },
                    )
                ],
            }
        )
