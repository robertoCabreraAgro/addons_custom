import math
from datetime import datetime

from dateutil.relativedelta import relativedelta

from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase


@tagged("payslip_dual_period")
class TestPayslipDualPeriod(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.payslip_obj = cls.env["hr.payslip"]
        cls.employee = cls.env.ref("hr.employee_qdp")
        cls.contract = cls.env.ref("hr_payroll.hr_contract_gilles_gravie")
        cls.contract.state = "open"
        cls.struct_id = cls.env.ref("hr_payroll.structure_worker_001")

    def test_001_compute_payslip_name(self):
        self.env.company.show_secondary_date_fields = True
        slip_name = self.struct_id.payslip_name = "Dual Period Slip"
        date_from = datetime.now().replace(day=1)
        date_to = datetime.now().replace(day=15)
        secondary_date_from = datetime.now().replace(day=5)
        secondary_date_to = datetime.now().replace(day=10)
        payslip_form = Form(self.env["hr.payslip"])
        payslip_form.employee_id = self.employee
        payslip_form.contract_id = self.contract
        payslip_form.struct_id = self.struct_id
        payslip_form.date_from = date_from.strftime("%Y-%m-%d")
        payslip_form.date_to = date_to.strftime("%Y-%m-%d")
        payslip_form.secondary_date_from = secondary_date_from.strftime("%Y-%m-%d")
        payslip_form.secondary_date_to = secondary_date_to.strftime("%Y-%m-%d")
        payslip = payslip_form.save()
        format_datef = secondary_date_from.strftime("%m/%d/%Y")
        format_datet = secondary_date_to.strftime("%m/%d/%Y")
        payslip_name = f"{slip_name} - {payslip.employee_id.legal_name} - {format_datef} - {format_datet}"
        self.assertEqual(payslip.name, payslip_name)
        secondary_date_from = date_from = datetime.now()
        secondary_date_to = date_to = date_from + relativedelta(months=1, days=-1)
        payslip_form = Form(payslip)
        payslip_form.date_from = date_from
        payslip_form.date_to = date_to
        payslip = payslip_form.save()
        format_datef = secondary_date_from.strftime("%B")
        format_datet = secondary_date_from.strftime("%Y")
        payslip_name = f"{slip_name} - {payslip.employee_id.legal_name} - {format_datef} {format_datet}"
        self.assertEqual(payslip.name, payslip_name)
        self.contract.schedule_pay = "quarterly"
        secondary_date_to = date_to = date_from + relativedelta(months=3, days=-1)
        payslip_form = Form(payslip)
        payslip_form.date_from = date_from
        payslip_form.date_to = date_to
        payslip = payslip_form.save()
        format_datef = math.ceil(date_from.month / 3)
        format_datet = date_from.strftime("%Y")
        payslip_name = f"{slip_name} - {payslip.employee_id.legal_name} - Quarter {format_datef} of {format_datet}"
        self.assertEqual(payslip.name, payslip_name)
        self.contract.schedule_pay = "annually"
        secondary_date_to = date_to = date_from + relativedelta(years=1, days=-1)
        payslip_form = Form(payslip)
        payslip_form.date_from = date_from
        payslip_form.date_to = date_to
        payslip = payslip_form.save()
        format_datef = date_from.strftime("%Y")
        payslip_name = (
            f"{slip_name} - {payslip.employee_id.legal_name} - {format_datef}"
        )
        self.assertEqual(payslip.name, payslip_name)
        self.contract.schedule_pay = "semi-annually"
        secondary_date_from = date_from = datetime.now().replace(day=1, month=6)
        secondary_date_to = date_to = date_from + relativedelta(months=6, days=-1)
        payslip_form = Form(payslip)
        payslip_form.date_from = date_from
        payslip_form.date_to = date_to
        payslip_form.secondary_date_from = secondary_date_from.strftime("%Y-%m-%d")
        payslip_form.secondary_date_to = secondary_date_to.strftime("%Y-%m-%d")
        payslip = payslip_form.save()
        year_half = date_from.replace(day=1, month=6)
        is_first_half = date_from < year_half
        format_datef = (
            f"1st semester of {date_from.year}"
            if is_first_half
            else f"2nd semester of {date_from.year}"
        )
        payslip_name = (
            f"{slip_name} - {payslip.employee_id.legal_name} - {format_datef}"
        )
        self.assertEqual(payslip.name, payslip_name)
        self.contract.schedule_pay = "weekly"
        secondary_date_from = date_from = datetime.now()
        secondary_date_to = date_to = date_from + relativedelta(days=6)
        payslip_form = Form(payslip)
        payslip_form.date_from = date_from
        payslip_form.date_to = date_to
        payslip_form.secondary_date_from = secondary_date_from.strftime("%Y-%m-%d")
        payslip_form.secondary_date_to = secondary_date_to.strftime("%Y-%m-%d")
        payslip = payslip_form.save()
        format_datef = date_from.strftime("%U")
        format_datet = date_from.strftime("%Y")
        payslip_name = f"{slip_name} - {payslip.employee_id.legal_name} - Week {format_datef} of {format_datet}"
        self.assertEqual(payslip.name, payslip_name)
