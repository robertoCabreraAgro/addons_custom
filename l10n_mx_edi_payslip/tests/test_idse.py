import unittest

from odoo import fields
from odoo.tests.common import tagged

from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@tagged("hr_idse", "post_install", "-at_install")
class TestHrIdse(TestAccountReportsCommon):
    def setUp(self):
        super().setUp()
        self.env["hr.contract"].search([]).write({"state": "draft"})
        self.contract = self.env.ref("l10n_mx_edi_payslip.hr_contract_maria").sudo()
        self.contract.state = "open"
        self.contract.company_id = self.env.company
        self.contract.employee_id.company_id = self.env.company
        self.contract.date_start = "2024-06-01"
        self.contract.l10n_mx_edi_sbc = 76648.0
        self.contract.employee_id.company_id.company_registry = "1203256"

    def test_001_insured(self):
        """Generated TXT for insured"""
        report = self.env.ref("l10n_mx_edi_payslip.idse_report")
        options = self._generate_options(
            report,
            fields.Date.from_string("2024-01-01"),
            fields.Date.from_string("2024-12-31"),
        )
        self.assertEqual(
            "\n".join(
                self.env[report.custom_handler_model_name]
                ._l10n_mx_txt_export(options)["file_content"]
                .decode()
                .split("\r\n")
            ),
            "1203256    12345678923OLIVIA                     MARTINEZ SAGAZ             MARIA                      "
            "076648      10001062024T21  08     {id}         PUXB571021HNELXR009\n".format(
                id=self.contract.employee_id.id
            ),
            "Error with IDSE generation",
        )

    def test_002_baja(self):
        """Generated TXT for baja"""
        self.env["hr.departure.wizard"].create(
            {
                "departure_reason_id": self.env.ref("hr.departure_fired").id,
                "employee_id": self.contract.employee_id.id,
            }
        ).sudo().action_register_departure()
        self.contract.employee_id.toggle_active()
        date = self.contract.employee_id.departure_date
        report = self.env.ref("l10n_mx_edi_payslip.idse_baja_report")
        options = self._generate_options(
            report,
            date.replace(month=1).replace(day=1),
            date.replace(month=12).replace(day=31),
        )
        self.assertEqual(
            "\n".join(
                self.env[report.custom_handler_model_name]
                ._l10n_mx_txt_export(options)["file_content"]
                .decode()
                .split("\r\n")
            ),
            "1203256    12345678923OLIVIA                     MARTINEZ SAGAZ             MARIA                      "
            "000000000000000{date}     02     {id}        1                  9\n".format(
                date=fields.datetime.strftime(date, "%d%m%Y"),
                id=self.contract.employee_id.id,
            ),
            "Error with IDSE generation",
        )

    @unittest.skip("Message tracking is not working on tests.")
    def test_003_wage(self):
        """Generated TXT for wage"""
        messages = self.contract.message_ids.filtered(
            lambda m: m.message_type == "notification"
        )
        tracking = (
            messages.sudo()
            .mapped("tracking_value_ids")
            .filtered(lambda t: t.field.name == "l10n_mx_edi_sbc")
        )
        date = tracking.sorted("create_date").create_date.date()

        report = self.env.ref("l10n_mx_edi_payslip.idse_wage_report")
        options = self._generate_options(
            report,
            date.replace(month=1).replace(day=1),
            date.replace(month=12).replace(day=31),
        )
        self.assertEqual(
            "\n".join(
                self.env[report.custom_handler_model_name]
                ._l10n_mx_txt_export(options)["file_content"]
                .decode()
                .split("\r\n")
            ),
            "1203256    12345678923OLIVIA                     MARTINEZ SAGAZ             MARIA                      "
            "076648      100{date}     07     {id}          PUXB571021HNELXR009\n".format(
                date=fields.datetime.strftime(date, "%d%m%Y"),
                id=self.contract.employee_id.id,
            ),
            "Error with IDSE generation",
        )
