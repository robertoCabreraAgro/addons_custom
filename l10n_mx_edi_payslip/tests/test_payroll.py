import base64
import time
import unittest
from datetime import date, datetime, time as dt_time, timedelta

from lxml import etree, objectify

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests.common import Form, tagged
from odoo.tools import float_is_zero, float_round

from .common import L10nMxEdiPayslipTransactionCase


@tagged("hr_payroll", "post_install", "-at_install")
class HRPayroll(L10nMxEdiPayslipTransactionCase):
    @unittest.skip("Blocking un-mocked external HTTP request")
    def test_001_xml_structure(self):
        """Use XML expected to verify that is equal to generated. And SAT
        status"""
        self.employee.sudo().contract_id = self.contract
        payroll = self.create_payroll()
        self.env["hr.payslip.overtime"].create(
            {
                "employee_id": self.employee.id,
                "name": "%s-%s-01" % (time.strftime("%Y"), time.strftime("%m")),
                "hours": 1,
            }
        )
        payroll.compute_sheet()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)
        self.env.ref("l10n_mx_edi_payslip.ir_cron_update_sat_status_payroll").sudo().method_direct_trigger()
        self.assertEqual(payroll.l10n_mx_edi_sat_status, "not_found")
        payroll.invalidate_recordset()
        xml = payroll.l10n_mx_edi_get_xml_etree()
        self.xml_expected.attrib["Fecha"] = xml.attrib["Fecha"]
        self.xml_expected.attrib["Folio"] = xml.attrib["Folio"]
        self.xml_expected.attrib["Sello"] = xml.attrib["Sello"]
        node_payroll = payroll.l10n_mx_edi_get_payroll_etree(xml)
        node_expected = payroll.l10n_mx_edi_get_payroll_etree(self.xml_expected)
        self.assertTrue(node_payroll is not None, "Complement to payroll not added.")
        node_expected.Receptor.attrib["FechaInicioRelLaboral"] = node_payroll.Receptor.attrib["FechaInicioRelLaboral"]
        node_expected.attrib["FechaFinalPago"] = node_payroll.attrib["FechaFinalPago"]
        node_expected.attrib["FechaInicialPago"] = node_payroll.attrib["FechaInicialPago"]
        node_expected.attrib["FechaPago"] = node_payroll.attrib["FechaPago"]
        node_expected.Receptor.attrib["Antig\xfcedad"] = node_payroll.Receptor.attrib["Antig\xfcedad"]

        # Replace node TimbreFiscalDigital
        tfd_expected = self.payslip_obj.l10n_mx_edi_get_tfd_etree(self.xml_expected)
        tfd_xml = objectify.fromstring(etree.tostring(self.payslip_obj.l10n_mx_edi_get_tfd_etree(xml)))
        self.xml_expected.Complemento.replace(tfd_expected, tfd_xml)
        self.assertEqualXML(xml, self.xml_expected)

    @unittest.skip("Blocking un-mocked external HTTP request")
    def test_002_perception_022(self):
        """When perception code have 022, the payroll have node SeparacionIndemnizacion."""
        self.struct = self.env.ref("l10n_mx_edi_payslip.payroll_structure_data_03")
        payroll = self.create_payroll()
        date_start = payroll.l10n_mx_edi_payment_date - timedelta(days=380)
        self.contract.write(
            {
                "date_start": date_start,
            }
        )
        payroll.compute_sheet()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)

    @unittest.skip("Blocking un-mocked external HTTP request")
    def test_003_perception_039(self):
        """When perception code have 039, the payroll have node
        JubilacionPensionRetiro."""
        payroll = self.create_payroll()
        payroll.write(
            {
                "input_line_ids": [
                    Command.create(
                        {
                            "code": "pe_039",
                            "name": "Jubilaciones, pensiones o haberes de retiro",
                            "amount": 1000.0,
                            "contract_id": self.contract.id,
                            "input_type_id": self.ref(
                                "l10n_mx_edi_payslip.hr_payslip_input_type_perception_039_e"
                            ),  # noqa
                        },
                    )
                ],
            }
        )
        payroll.compute_sheet()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)

    @unittest.skip("Blocking un-mocked external HTTP request")
    def test_004_other_payment_004(self):
        """When other payment have the code 004, this must have node
        CompensacionSaldosAFavor."""
        payroll = self.create_payroll()
        payroll.write(
            {
                "input_line_ids": [
                    Command.create(
                        {
                            "code": "op_004",
                            "name": "Aplicación de saldo a favor por compensación anual.",
                            "amount": 500.0,
                            "contract_id": self.contract.id,
                            "input_type_id": self.ref(
                                "l10n_mx_edi_payslip.hr_payslip_input_type_other_payment_004"
                            ),  # noqa
                        },
                    )
                ],
                "l10n_mx_edi_balance_favor": 500.0,
                "l10n_mx_edi_comp_year": (datetime.today()).year - 1,
                "l10n_mx_edi_remaining": 500.0,
            }
        )
        payroll.compute_sheet()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)

    @unittest.skip("Blocking un-mocked external HTTP request")
    def test_005_perception_045(self):
        """When one perception have the code 045, this must have node
        AccionesOTitulos,."""
        payroll = self.create_payroll()
        payroll.write(
            {
                "input_line_ids": [
                    Command.create(
                        {
                            "code": "pe_045",
                            "name": "Ingresos en acciones o títulos valor que representan bienes",  # noqa
                            "amount": 500.0,
                            "contract_id": self.contract.id,
                            "input_type_id": self.ref(
                                "l10n_mx_edi_payslip.hr_payslip_input_type_perception_045_e"
                            ),  # noqa
                        },
                    )
                ],
                "l10n_mx_edi_action_title_ids": [
                    Command.create(
                        {
                            "category_id": self.cat_excempt.id,
                            "market_value": 100.0,
                            "price_granted": 100.0,
                        },
                    )
                ],
            }
        )
        payroll.compute_sheet()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)

    @unittest.skip("Review this test to print pdf")
    def test_006_print_pdf(self):
        """Verify that PDF is generated"""
        payroll = self.create_payroll()
        payroll.compute_sheet()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)
        report = self.env.ref("hr_payroll.action_report_payslip", False)
        pdf_content, _content_type = report._render_qweb_pdf(payroll.id)
        self.assertTrue(pdf_content, "Report not generated.")

    @unittest.skip("Blocking un-mocked external HTTP request")
    def test_007_cancel_xml(self):
        """Verify that XML is cancelled"""
        payroll = self.create_payroll()
        # It is just created, should can be cancelled without problems
        payroll.action_payslip_cancel()
        payroll.action_payslip_draft()
        payroll.compute_sheet()
        payroll.action_payslip_done()
        # It is just created and confirmed, not signed should can be cancelled without problems
        payroll.action_payslip_cancel()
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "cancelled", payroll.l10n_mx_edi_error)
        payroll.action_payslip_draft()
        payroll.compute_sheet()
        payroll.action_payslip_done()
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "to_sign", payroll.l10n_mx_edi_error)
        payroll.l10n_mx_edi_update_pac_status()
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)
        payroll._compute_cfdi_values()
        with self.assertRaises(
            UserError,
            msg="You have selected signed payslips. Please, use the option Request Edi "
            "Cancellation instead directly cancelling the payslip",
        ):
            payroll.action_payslip_cancel()
        with self.assertRaises(UserError, msg="In order to allow cancel, please define the cancellation case."):
            payroll.l10n_mx_edi_action_request_edi_cancel()
        # Cancel with the reason 03 should be cancelled just than before.
        payroll.l10n_mx_edi_cancellation = "03"
        payroll.l10n_mx_edi_action_request_edi_cancel()
        payroll.l10n_mx_edi_update_pac_status()
        self.assertTrue(payroll.l10n_mx_edi_pac_status in ("to_cancel", "cancelled"), payroll.l10n_mx_edi_error)

        # Test cancelation case 01
        payroll = self.create_payroll()
        payroll.compute_sheet()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)
        payroll._compute_cfdi_values()
        payroll.l10n_mx_edi_cancellation = "01"
        payroll.l10n_mx_edi_action_request_edi_cancel()
        self.assertEqual(payroll.state, "cancel")
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "to_cancel", payroll.l10n_mx_edi_error)
        # Create substitute payslip
        substitute_payroll = self.create_payroll()
        substitute_payroll.compute_sheet()
        substitute_payroll.l10n_mx_edi_origin = "04|%s" % payroll.l10n_mx_edi_cfdi_uuid
        substitute_payroll.action_payslip_done()
        substitute_payroll.l10n_mx_edi_update_pac_status()
        self.assertEqual(substitute_payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)
        self.assertEqual(
            payroll.l10n_mx_edi_cancel_payslip_id,
            substitute_payroll,
            "The substitute pay slip should be auto assigned to the first payslip",
        )
        payroll.l10n_mx_edi_update_pac_status()
        self.assertTrue(payroll.l10n_mx_edi_pac_status in ("to_cancel", "cancelled"), payroll.l10n_mx_edi_error)

    def test_008_send_payroll_mail(self):
        """Verify that XML is attach on wizard that send mail"""
        payroll = self.create_payroll()
        payroll.compute_sheet()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        mail_data = payroll.action_payroll_sent()
        template = mail_data.get("context", {}).get("default_template_id", [])
        template = self.env["mail.template"].browse(template)
        mail_composer_form = Form(
            self.env["mail.compose.message"].with_context(
                **{
                    "default_model": "hr.payslip",
                    "default_template_id": template and template.id or False,
                    "default_composition_mode": "comment",
                    "default_res_ids": payroll.ids,
                }
            )
        )
        mail_composer = mail_composer_form.save()
        mail_composer.action_send_mail()
        self.assertEqual(len(mail_composer.attachment_ids), 2, "Documents not attached")
        self.assertTrue(payroll.sent, "Sent field is not marked in the slip.")

    @unittest.skip("Blocking un-mocked external HTTP request")
    def test_009_batches(self):
        """Verify payroll information and confirm payslips from batches
        Verify fiscal position on account move generation"""
        self.employee += self.prepare_second_employee(True)
        payment_date = (datetime.today() + timedelta(days=5)).strftime("%Y-%m-%d")
        self.contract.state = "open"
        payslip_run = self.payslip_run_obj.create(
            {
                "name": "Payslip VX",
                "l10n_mx_edi_payment_date": payment_date,
            }
        )
        payslip_run.write(
            {
                "l10n_mx_edi_date_start": payslip_run.date_start,
                "l10n_mx_edi_date_end": payslip_run.date_end,
            }
        )
        self.regenerate_work_entries()
        self.wizard_batch.create(
            {
                "employee_ids": [Command.set(self.employee.ids)],
                "structure_id": self.struct.id,
            }
        ).with_context(active_id=payslip_run.id).compute_sheet()
        for slip in payslip_run.slip_ids:
            self.assertEqual(
                slip.l10n_mx_edi_payment_date.strftime("%Y-%m-%d"),
                payment_date,
                "Payment date not assigned in a payroll created.",
            )
            self.assertEqual(
                slip.l10n_mx_edi_date_from,
                payslip_run.l10n_mx_edi_date_start,
                "Date from not assigned in the payroll created.",
            )
            self.assertEqual(
                slip.l10n_mx_edi_date_to,
                payslip_run.l10n_mx_edi_date_end,
                "Date to not assigned in the payroll created.",
            )

        # Action that generate the overtimes
        payslip_run.slip_ids.mapped("contract_id").write({"l10n_mx_edi_allow_overtimes": True})
        payslip_run.action_set_overtimes()
        overtimes = self.env["hr.payslip.overtime"].search(
            [("employee_id", "in", payslip_run.slip_ids.mapped("employee_id").ids)]
        )
        self.assertTrue(overtimes, "Overtimes not generated for the employee")
        overtimes.unlink()

        payslip_run.slip_ids.write({"l10n_mx_edi_source_resource": "IP"})
        payslip_run.action_validate()
        payslip_run.action_payslips_done()
        self.env.ref("l10n_mx_edi_payslip.ir_cron_mx_edi_payslip_web_services").sudo().method_direct_trigger()
        for slip in payslip_run.slip_ids:
            self.assertEqual(slip.l10n_mx_edi_pac_status, "signed", slip.l10n_mx_edi_error)
        # Test lines generated in account move
        move_id = payslip_run.slip_ids.mapped("move_id")
        salary_lines = move_id.mapped("line_ids").filtered(
            lambda line: line.name == "Sueldos, Salarios Rayas y Jornales"
        )
        self.assertEqual(len(salary_lines), 2, "There should be 2 lines for sueldos, salarios... in the account move")
        accounts = salary_lines.mapped("account_id")
        account1 = self.env.ref("l10n_mx_edi_payslip.cuenta601_08").id
        account1 = accounts.filtered(lambda a, account1=account1: a.id == account1)
        self.assertTrue(account1, "In the account move, should be a line for the account")
        account2 = accounts.filtered(lambda a: "601.84.01" in a.code)
        self.assertTrue(account2, "In the account move, should be a line for the account")

        # Ensure that dispersions action works correctly
        self.env.ref("hr_bank_dispersion.allow_print_payslip_dispersion").sudo().write(
            {"users": [Command.link(self.env.user.id)]}
        )
        payslip_run._get_payslips_dispersions()

        # Ensure that sent action works correctly
        # TODO: Remove this group assignation
        self.env.ref("hr.group_hr_manager", False).sudo().write({"users": [Command.link(self.env.user.id)]})
        payslip_run.sudo().action_payroll_sent()
        self.assertTrue(
            all(payslip_run.slip_ids.mapped("sent")),
            "At least one of the sent fields in the slip list was not marked as true.",
        )

        report = self.env["ir.actions.report"]._get_report_from_name("l10n_mx_edi_payslip.raya_list_report")
        self.assertEqual(len(report._render(report.id, payslip_run.id)), 2)

    def test_010_aguinaldo(self):
        """When in payslip has a perception of Christmas bonuses (Aguinaldo)"""
        self.struct = self.env.ref("l10n_mx_edi_payslip.payroll_structure_data_02")
        payroll = self.create_payroll()
        start_date = payroll.l10n_mx_edi_payment_date - timedelta(days=380)
        self.contract.write(
            {
                "date_start": start_date,
            }
        )
        payroll.compute_sheet()
        payroll.action_payslip_done()
        # Mute: Blocking un-mocked external HTTP request
        # payroll.l10n_mx_edi_update_pac_status()
        # self.assertEqual(payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)
        # xml = payroll.l10n_mx_edi_get_xml_etree()
        # node_payroll = payroll.l10n_mx_edi_get_payroll_etree(xml)
        # self.assertEqual("11000.00", node_payroll.get("TotalPercepciones", ""))

    @unittest.skip("Blocking un-mocked external HTTP request")
    def test_012_resign_process(self):
        """Tests the re-sign process (recovery a previously signed xml)"""
        payroll = self.create_payroll()
        payroll.compute_sheet()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)
        xml_attachs = payroll.l10n_mx_edi_retrieve_attachments()
        self.assertEqual(len(xml_attachs), 1)
        xml_1 = objectify.fromstring(base64.b64decode(xml_attachs[0].datas))
        payroll.l10n_mx_edi_pac_status = "retry"
        for _x in range(10):
            if payroll.l10n_mx_edi_pac_status == "signed":
                break
            time.sleep(2)
            payroll.l10n_mx_edi_retrieve_last_attachment().unlink()
            payroll.l10n_mx_edi_update_pac_status()
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)
        xml_attachs = payroll.l10n_mx_edi_retrieve_attachments()
        self.assertEqual(len(xml_attachs), 1, "There should be just one xml")
        xml_2 = objectify.fromstring(base64.b64decode(xml_attachs[0].datas))
        self.assertEqualXML(xml_1, xml_2)

    @unittest.skip("Blocking un-mocked external HTTP request")
    def test_013_assimilated(self):
        """Tests case when the employee is assimilated"""
        payroll = self.create_payroll()
        payroll.employee_id.sudo().l10n_mx_edi_is_assimilated = True
        payroll.employee_id.sudo().l10n_mx_edi_contract_regime_type = "09"
        payroll.contract_id.sudo().contract_type_id = self.env.ref("l10n_mx_edi_payslip.hr_contract_type_99")
        payroll.compute_sheet()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)

    @unittest.skip("Blocking un-mocked external HTTP request")
    def test_014_allow_validate_payslip(self):
        """Test case when an employee"""
        payroll = self.create_payroll()
        payroll.compute_sheet()
        # remove permission group to perform the test
        group_e = self.env.ref("l10n_mx_edi_payslip.allow_validate_payslip", False)
        group_e.sudo().write({"users": [(3, self.env.user.id)]})
        with self.assertRaises(
            UserError, msg="Only Managers who are allow to validate payslip can perform this operation"
        ):
            payroll.action_payslip_done()
        # Get back permission group and finish to test normal flow
        group_e.sudo().write({"users": [Command.link(self.env.user.id)]})
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)

    @unittest.skip("Blocking un-mocked external HTTP request")
    def test_015_alimony(self):
        """Test case with alimony in the employee. Also test the report
        Seven alimony types. Alimony expected amounts
        1. 110.0    2. 90.97    3. 100.0    4. 65.42
        5. 110.4    6. 73.17    7. 70.13
        """
        # Make sure the amounts, are what expected
        self.contract.wage = 22000.00
        self.employee.sudo().l10n_mx_edi_alimony_ids = [
            Command.create(
                {
                    "name": "Percentage over salary",
                    "number": "1",
                    "discount_type": "percentage_wage",
                    "discount_amount": 1,
                    "date_from": "%s-%s-01" % (time.strftime("%Y"), time.strftime("%m")),
                },
            ),
            Command.create(
                {
                    "name": "Percentage over perceptions less ISR and SS",
                    "number": "2",
                    "discount_type": "percentage_perceptions_ISR",
                    "discount_amount": 1,
                    "date_from": "%s-%s-01" % (time.strftime("%Y"), time.strftime("%m")),
                },
            ),
            Command.create(
                {
                    "name": "Amount fixed",
                    "number": "3",
                    "discount_type": "amount_fixed",
                    "discount_amount": 100,
                    "date_from": "%s-%s-01" % (time.strftime("%Y"), time.strftime("%m")),
                },
            ),
            Command.create(
                {
                    "name": "Percentage over net",
                    "number": "4",
                    "discount_type": "percentage_over_net",
                    "discount_amount": 1,
                    "date_from": "%s-%s-01" % (time.strftime("%Y"), time.strftime("%m")),
                },
            ),
            Command.create(
                {
                    "name": "Percentage over perceptions",
                    "number": "5",
                    "discount_type": "percentage_perceptions",
                    "discount_amount": 1,
                    "date_from": "%s-%s-01" % (time.strftime("%Y"), time.strftime("%m")),
                },
            ),
            Command.create(
                {
                    "name": "Percentage over perceptions less ISR and Mortgages",
                    "number": "6",
                    "discount_type": "percentage_perceptions_ISR_mortgages",
                    "discount_amount": 1,
                    "date_from": "%s-%s-01" % (time.strftime("%Y"), time.strftime("%m")),
                },
            ),
            Command.create(
                {
                    "name": "Percentage over perceptions less ISR, Social Security and Mortgages",
                    "number": "7",
                    "discount_type": "percentage_perceptions_ISR_mortgages_ss",
                    "discount_amount": 1,
                    "date_from": "%s-%s-01" % (time.strftime("%Y"), time.strftime("%m")),
                },
            ),
        ]
        payroll = self.create_payroll()
        payroll.compute_sheet()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)
        # Test Report
        # TODO: Enable
        # report = self.env["hr.alimony.report"]
        # options = self._generate_options(
        #     report, fields.Date.from_string("2022-01-01"), fields.Date.from_string("2022-12-31")
        # )
        # total_line = report._get_lines(options)[-1]
        # self.assertEqual(total_line["name"], "Total", "The last line must be the Total")
        # total_perceptions = total_line["columns"][3]["name"]
        # total_isr = total_line["columns"][4]["name"]
        # total_alimony = total_line["columns"][5]["name"]
        # self.assertEqual(total_perceptions, 78677.2, "Total Perceptions must be 78677.2")
        # self.assertEqual(total_isr, 11469.92, "Total Isr must be 11469.92")
        # self.assertEqual(total_alimony, 620.09, "Total Alimony must be 620.09")

    def test_016_loans(self):
        """Ensure that loan is created correctly"""
        payroll = self.create_payroll()
        payroll.compute_sheet()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        loan = self.env.ref("l10n_mx_edi_payslip.infonavit_qdp")
        loan._compute_payslips_count()
        self.assertEqual(loan.payslips_count, 1, "Payslip not applied in the loan.")
        self.employee.sudo()._compute_loan_count()
        self.assertEqual(self.employee.loan_count, 1, "Loan not found.")

    def test_017_allocations(self):
        """Ensure that allocations are generated"""
        holiday = self.env.ref("l10n_mx_edi_payslip.mexican_holiday")
        mexico_tz = self.env["l10n_mx_edi.certificate"]._get_timezone()
        date_mx = datetime.now(mexico_tz)
        self.contract.date_start = date_mx.replace(year=date_mx.year - 1)
        self.contract.state = "open"
        self.env.ref("l10n_mx_edi_payslip.ir_cron_create_mx_allocation").sudo().method_direct_trigger()
        allocation = self.env["hr.leave.allocation"].search(
            [("employee_id", "=", self.employee.id), ("name", "=", "%s MX %s" % (holiday.name, date_mx.year))]
        )
        self.assertTrue(allocation, "Allocation not generated")
        self.assertEqual(allocation.number_of_days, 12.0, "The contract has a year, the expected days are 12")

    @unittest.skip("Blocking un-mocked external HTTP request")
    def test_018_inabilities(self):
        """Ensure that inabilities are created"""
        self.remove_leaves()
        self.contract.resource_calendar_id.tz = self.employee.tz = self.env.user.tz = "America/Mexico_City"
        self.contract.write(
            {
                "state": "open",
            }
        )
        leave = self.env["hr.leave"].create(
            {
                "holiday_type": "employee",
                "employee_id": self.employee.id,
                "holiday_status_id": self.env.ref("l10n_mx_edi_payslip.mexican_maternity").id,
                "request_date_from": "%s-%s-01" % (time.strftime("%Y"), time.strftime("%m")),
                "request_date_to": "%s-%s-03" % (time.strftime("%Y"), time.strftime("%m")),
                "number_of_days": 3,
            }
        )
        # TODO: Review: This regenerate work entries should not be needed, maybe a odoo's ticket is needed
        self.regenerate_work_entries()
        leave._compute_date_from_to()
        leave.action_approve()
        #        self.regenerate_work_entries()
        payroll = self.create_payroll()
        payroll.action_refresh_from_work_entries()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.check_inability_node(payroll, "03", "3")
        # Base + finiquito
        self.struct = self.env.ref("l10n_mx_edi_payslip.payroll_structure_data_06")
        payroll = self.create_payroll()
        payroll.action_refresh_from_work_entries()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.check_inability_node(payroll, "03", "3")

    def check_inability_node(self, payroll, i_type, days):
        """Check if the Incapacidad node was created as expected.
        :param payroll: A payroll object already signed
        :type payroll: hr.payslip
        :param i_type: Inhability type according SAT catalog
        :type i_type: string
        :param days: Expected days in the node. Integer as a string
        :type days: string
        """
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)
        xml = payroll.l10n_mx_edi_get_xml_etree()
        self.assertEqual(
            i_type,
            payroll.l10n_mx_edi_get_payroll_etree(xml).Incapacidades.Incapacidad.get("TipoIncapacidad"),
            "Inability not added.",
        )
        self.assertEqual(
            days,
            payroll.l10n_mx_edi_get_payroll_etree(xml).Incapacidades.Incapacidad.get("DiasIncapacidad"),
            "Days in CFDI does not match with the leave.",
        )

    @unittest.skip("Blocking un-mocked external HTTP request")
    def test_019_inabilities(self):
        """Ensure that inabilities are created"""
        self.remove_leaves()
        self.contract.resource_calendar_id.tz = self.employee.tz = self.env.user.tz = "America/Mexico_City"
        self.contract.write(
            {
                "state": "open",
            }
        )
        leave = self.env["hr.leave"].create(
            {
                "holiday_type": "employee",
                "employee_id": self.employee.id,
                "holiday_status_id": self.env.ref("l10n_mx_edi_payslip.mexican_riesgo_de_trabajo").id,
                "request_date_from": "%s-%s-01" % (time.strftime("%Y"), time.strftime("%m")),
                "request_date_to": "%s-%s-03" % (time.strftime("%Y"), time.strftime("%m")),
                "number_of_days": 3,
            }
        )
        leave._compute_date_from_to()
        leave.action_approve()
        # TODO: Review: This regenerate work entries should not be needed, maybe a odoo's ticket is needed
        self.regenerate_work_entries()
        payroll = self.create_payroll()
        payroll.action_refresh_from_work_entries()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.check_inability_node(payroll, "01", "3")
        # Base + finiquito
        self.struct = self.env.ref("l10n_mx_edi_payslip.payroll_structure_data_06")
        payroll = self.create_payroll()
        payroll.action_refresh_from_work_entries()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.check_inability_node(payroll, "01", "3")

    @unittest.skip("Blocking un-mocked external HTTP request")
    def test_020_inabilities(self):
        """Ensure that inability for 'Enfermedad General' created"""
        self.remove_leaves()
        self.contract.resource_calendar_id.tz = self.employee.tz = self.env.user.tz = "America/Mexico_City"
        self.contract.write(
            {
                "state": "open",
            }
        )
        leave = self.env["hr.leave"].create(
            {
                "holiday_type": "employee",
                "employee_id": self.employee.id,
                "holiday_status_id": self.env.ref("l10n_mx_edi_payslip.mexican_enfermedad_general").id,
                "request_date_from": "%s-%s-01" % (time.strftime("%Y"), time.strftime("%m")),
                "request_date_to": "%s-%s-07" % (time.strftime("%Y"), time.strftime("%m")),
                "number_of_days": 7,
            }
        )
        # TODO: Review: This regenerate work entries should not be needed, maybe a odoo's ticket is needed
        self.regenerate_work_entries()
        leave._compute_date_from_to()
        leave.action_approve()
        payroll = self.create_payroll()
        payroll.action_refresh_from_work_entries()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.check_inability_node(payroll, "02", "7")
        # Base + finiquito
        self.struct = self.env.ref("l10n_mx_edi_payslip.payroll_structure_data_06")
        payroll = self.create_payroll()
        payroll.action_refresh_from_work_entries()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.check_inability_node(payroll, "02", "7")

    @unittest.skip("Blocking un-mocked external HTTP request")
    def test_021_inabilities(self):
        """Ensure that inability for 'Hijos con Cancer' is created"""
        self.remove_leaves()
        self.contract.resource_calendar_id.tz = self.employee.tz = self.env.user.tz = "America/Mexico_City"
        self.contract.write(
            {
                "state": "open",
            }
        )
        leave = self.env["hr.leave"].create(
            {
                "holiday_type": "employee",
                "employee_id": self.employee.id,
                "holiday_status_id": self.env.ref("l10n_mx_edi_payslip.mexican_licencia_padres_hijo_cancer").id,
                "request_date_from": "%s-%s-01" % (time.strftime("%Y"), time.strftime("%m")),
                "request_date_to": "%s-%s-03" % (time.strftime("%Y"), time.strftime("%m")),
                "number_of_days": 3,
            }
        )
        leave._compute_date_from_to()
        leave.action_approve()
        # TODO: Review: This regenerate work entries should not be needed, maybe a odoo's ticket is needed
        self.regenerate_work_entries()
        payroll = self.create_payroll()
        payroll.action_refresh_from_work_entries()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.check_inability_node(payroll, "04", "3")
        # Base + finiquito
        self.struct = self.env.ref("l10n_mx_edi_payslip.payroll_structure_data_06")
        payroll = self.create_payroll()
        payroll.action_refresh_from_work_entries()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.check_inability_node(payroll, "04", "3")

    def test_022_working_days(self):
        """Ensure that worked days is correct with new contracts"""
        self.contract.date_start = self.contract.date_start + timedelta(days=5)
        payroll = self.create_payroll()
        payroll.action_refresh_from_work_entries()
        self.assertEqual(15, sum(payroll.worked_days_line_ids.mapped("number_of_days")), "Total days incorrect")

    def test_023_get_dates_on_datetime(self):
        """Ensure payslips dates are converted correctly to employee timezones"""
        self.employee.sudo().tz = "America/Mazatlan"
        payroll = self.create_payroll(date(2020, 11, 16), date(2020, 11, 30))
        date_from, date_to = payroll._get_dates_on_datetime()
        self.assertEqual(date_from, datetime(2020, 11, 16, 7, 6), "Date from incorrectly converted")
        self.assertEqual(date_to, datetime(2020, 12, 1, 7, 5, 59), "Date to incorrectly converted")

    @unittest.skip("FIXME activate again when the time zone issue is resolved")
    def test_024_public_time_off_creation(self):
        """Correct creation of public time off"""
        # TODO: Expand this test, cover payslip affectations
        self.env.user.tz = "America/Denver"
        public_holiday = self.env["l10n_mx_edi.public.holiday"].create(
            {
                "name": "Thanksgiving",
                "date": date.today(),
            }
        )
        public_holiday.action_confirm()  # This method was depreciated in v17
        self.assertEqual(public_holiday.state, "validate", "Public Holiday not Validated")
        global_leave = self.env["resource.calendar.leaves"].search([("name", "=", "Thanksgiving")])[0]
        self.assertTrue(global_leave, "Global leave not created")
        expected_date_from = datetime.combine(date.today(), dt_time(7, 0))
        self.assertEqual(global_leave.date_from, expected_date_from, "Incorrect Date To on Leave")
        expected_date_to = expected_date_from + timedelta(days=1, seconds=-1)
        self.assertEqual(global_leave.date_to, expected_date_to, "Incorrect Date from on Leave")

    def test_025_onchange_date_errors(self):
        # TODO: Review: this test must be redesigned
        payroll = self.create_payroll()
        payroll.compute_sheet()
        # Attendances to check salary rules prima dominical, septimo dia and dias de descanso trabajados
        self.generate_attendances(self.employee, payroll.date_from, payroll.date_from + timedelta(days=8))
        # Test Onchange date errors
        form = Form(payroll)
        form.date_to = payroll.date_to - timedelta(days=1)
        form.save()
        self.assertEqual(payroll.date_to.strftime("%Y-%m-%d"), form.date_to, "The date was not updated.")

    def test_026_mexican_holiday_allocation(self):
        """Test the cron for automatic Mexican Holiday allocation
        Create an allocation that is the allocation from the last year.
        Call the cron to create the new allocation.
        Check that the last year allocation now is refused
        Check if now there are two allocations, the another one is not related so should be there.
        Check the new year allocation."""
        self.employee.tz = self.contract.resource_calendar_id.tz = self.env.user.tz
        self.employee.parent_id = False
        holiday = self.env.ref("l10n_mx_edi_payslip.mexican_holiday")
        mexico_tz = self.env["l10n_mx_edi.certificate"]._get_timezone()
        date_mx = datetime.now(mexico_tz)
        self.contract.state = "open"
        self.contract.date_start = date_mx.replace(year=date_mx.year - 2)
        self.remove_leaves()

        # Create an allocation for the last year
        old_allocation = self.allocation_obj.create(
            {
                "name": "%s MX %s" % (holiday.name, (date_mx.year - 1)),
                "holiday_status_id": holiday.id,
                "number_of_days": 6,
                "holiday_type": "employee",
                "employee_id": self.employee.id,
                "state": "confirm",
                "allocation_type": "regular",
                "date_from": date_mx.replace(year=date_mx.year - 1),
                "date_to": date_mx - timedelta(days=1),
            }
        )
        old_allocation.action_validate()
        # Use Cron, update the holidays. The old allocation should not be refused
        self.env.ref("l10n_mx_edi_payslip.ir_cron_create_mx_allocation").sudo().method_direct_trigger()
        self.assertEqual(old_allocation.state, "validate", "The allocation should not be refused")
        allocations = self.allocation_obj.search(
            [
                ("employee_id", "=", self.employee.id),
                ("state", "=", "validate"),
                ("holiday_status_id", "=", holiday.id),
            ]
        )
        self.assertEqual(len(allocations), 2, "There should be two allocations, for the actual and the last year")
        new_allocation = allocations - old_allocation
        self.assertTrue(new_allocation, "The allocation for the next holiday period was not created")
        self.assertEqual(
            new_allocation.name,
            "%s MX %s" % (holiday.name, (date_mx.year)),
            "The allocation created by the cron should be named as the actual year",
        )
        # Ensure that holiday is available and paid in the payslip
        payroll = self.create_payroll()
        leave = self.env["hr.leave"].create(
            {
                "holiday_type": "employee",
                "employee_id": self.employee.id,
                "holiday_status_id": holiday.id,
            }
        )
        leave = Form(leave)
        leave.request_date_from = "%s-%s-01" % (time.strftime("%Y"), time.strftime("%m"))
        leave.request_date_to = "%s-%s-03" % (time.strftime("%Y"), time.strftime("%m"))
        leave = leave.save()
        # TODO: Review: This regenerate work entries should not be needed, maybe a odoo's ticket is needed
        self.regenerate_work_entries()
        leave.action_approve()
        payroll.action_refresh_from_work_entries()
        payroll.compute_sheet()
        self.assertTrue(
            self.env.ref("l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_perception_001_holidays")
            in payroll.line_ids.mapped("salary_rule_id"),
            "Holidays not paid.",
        )

    @unittest.skip("Blocking un-mocked external HTTP request")
    def test_027_extra_dinamic_concepts_cfdi(self):
        """Check dinamic concepts on cfdi"""
        self.contract.state = "open"
        payroll = self.create_payroll()
        payroll.compute_sheet()
        input_type_id = self.env.ref("l10n_mx_edi_payslip.hr_payslip_input_type_perception_028_g")
        extras = self.env["hr.payslip.extra"].create(
            {
                "name": "Payslip Extras Test",
                "input_id": input_type_id.id,
                "date": payroll.l10n_mx_edi_payment_date,
                "detail_ids": [
                    Command.create(
                        {
                            "employee_id": self.employee.id,
                            "amount": 3255.0,
                            "name": "Commission ABC",
                        },
                    ),
                    Command.create(
                        {
                            "employee_id": self.employee.id,
                            "amount": 1520.0,
                            "name": "Commission DEF",
                        },
                    ),
                ],
            }
        )
        extras.action_approve()
        payroll.l10n_mx_edi_update_extras()
        input_line = payroll.input_line_ids.filtered(lambda line, code=input_type_id.code: line.code == code)
        self.assertTrue(input_line, "The input for Commission was not created")
        code = input_line[0].code
        code = "%s%s" % (code.split("_")[0].upper(), code.split("_")[1])
        payslip_line = payroll.line_ids.filtered(lambda line, code=code: line.code == code)
        self.assertEqual(payslip_line.amount, 4775.0, "The commision payslip line amount must be 4775.0")
        # Check l10n_mx_edi_dynamic_name
        self.assertEqual(
            payslip_line.name,
            payroll.l10n_mx_edi_name(payslip_line),
            "The name returned name must be the normal line name",
        )
        # Activate l10n_mx_edi_dynamic_name
        payroll.company_id.sudo().l10n_mx_edi_dynamic_name = True
        expected_name = "%s: %s" % (payslip_line.name, ", ".join(extras.detail_ids.mapped("name")))
        self.assertEqual(
            expected_name, payroll.l10n_mx_edi_name(payslip_line), "The name returned name must be %s" % expected_name
        )
        # Check the line string on the CFDI
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)
        xml = payroll.l10n_mx_edi_get_xml_etree()
        node_payroll = payroll.l10n_mx_edi_get_payroll_etree(xml)
        commission_node = None
        for perception in node_payroll.Percepciones.Percepcion:
            if perception.get("Clave") == code:
                commission_node = perception
                break
        self.assertTrue(commission_node, "The node for commisions were not created.")
        self.assertEqual(
            expected_name, commission_node.attrib["Concepto"], "The name returned name must be %s" % expected_name
        )

        # Check when the extras have not details string
        new_payroll = payroll.copy()
        extras.action_cancel()
        extras.mapped("detail_ids").write({"name": False})
        extras.action_approve()
        new_payroll.l10n_mx_edi_update_extras()
        new_payroll.action_payslip_done()
        new_payroll.l10n_mx_edi_update_pac_status()
        self.assertEqual(new_payroll.l10n_mx_edi_pac_status, "signed", new_payroll.l10n_mx_edi_error)

    def test_028_out_of_contract(self):
        """Test out of contract worked days and recompute worked days method"""
        self.remove_leaves()
        payroll = self.create_payroll()
        # Check the contract starts much time before
        self.contract.date_start = payroll.date_from - timedelta(days=405)
        self.contract.date_end = payroll.date_to - timedelta(days=5)
        self._check_out_of_contract_config(payroll, 5)
        # Check the contract starts after payslip period and has no end
        self.contract.date_start = payroll.date_from + timedelta(days=5)
        self.contract.date_end = False
        self._check_out_of_contract_config(payroll, 5)
        # Check the contract starts after payslip period and has end after payslip period
        self.contract.date_start = payroll.date_from + timedelta(days=5)
        self.contract.date_end = payroll.date_to + timedelta(days=35)
        self._check_out_of_contract_config(payroll, 5)
        # Check if the contract ends before the period
        self.contract.date_start = payroll.date_from
        self.contract.date_end = payroll.date_to - timedelta(days=5)
        self._check_out_of_contract_config(payroll, 5)
        # Check if the contract starts after payslip period and ends before the period
        self.contract.date_start = payroll.date_from + timedelta(days=3)
        self.contract.date_end = payroll.date_to - timedelta(days=3)
        self._check_out_of_contract_config(payroll, 6)

    @unittest.skip("Blocking un-mocked external HTTP request")
    def test_029_schedule_action_pac_sign(self):
        """Test the normal flow for the schedule action to sign the payslips
        Create one or more payslips prepere them to be sign and sign them by the action"""
        payroll = self.create_payroll()
        payroll.compute_sheet()
        payroll.action_payslip_done()
        payroll2 = self.create_payroll()
        payroll2.compute_sheet()
        payroll2.action_payslip_done()
        self.env.ref("l10n_mx_edi_payslip.ir_cron_mx_edi_payslip_web_services").sudo().method_direct_trigger()
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)
        self.assertEqual(payroll2.l10n_mx_edi_pac_status, "signed", payroll2.l10n_mx_edi_error)

    @unittest.skip("Blocking un-mocked external HTTP request")
    def test_030_expected_sign_fails_catch_flow(self):
        """When a configuration or sign fail is showing the error should be managed, this test checks if
        the error the catch flow is working as expected"""
        # Error on sign/sent to pac. Invalid RFC
        self.employee.l10n_mx_edi_private_vat = "MAR980114GQR"
        payroll = self.create_payroll()
        payroll.compute_sheet()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "retry", "The sign must fail, The pac status must be Retry")
        self.assertTrue(payroll.l10n_mx_edi_error, "The sign must fail, the error variable must show a message")

    def test_031_change_struct_in_end_contract(self):
        """Verify payroll information and confirm payslips from batches
        Verify fiscal position on account move generation"""
        self.env.company.sudo().write({"l10n_mx_edi_automatic_settlement": True})
        employees = self.employee | self.prepare_second_employee()
        # Adding a third employee using the new end date
        self.contract.date_end = date.today().replace(day=15)
        employees |= self.prepare_second_employee()
        self.contract.state = "open"
        payslip_run = self.payslip_run_obj.create(
            {
                "name": "Payslip VX",
                "date_start": "%s-%s-01" % (time.strftime("%Y"), time.strftime("%m")),
                "date_end": "%s-%s-15" % (time.strftime("%Y"), time.strftime("%m")),
                "l10n_mx_edi_payment_date": "%s-%s-15" % (time.strftime("%Y"), time.strftime("%m")),
            }
        )
        self.env["hr.work.entry"].sudo().search([]).unlink()
        employees.generate_work_entries(payslip_run.date_start, payslip_run.date_end, True)
        self.wizard_batch.create(
            {
                "employee_ids": [Command.set(employees.ids)],
                "structure_id": self.struct.id,
            }
        ).with_context(active_id=payslip_run.id).compute_sheet()
        self.assertEqual(len(payslip_run.slip_ids), 3, "There must be 3 payslips in the batch")
        struct_bf = self.env.ref("l10n_mx_edi_payslip.payroll_structure_data_06")
        slips = payslip_run.slip_ids.filtered(lambda slip, struct_bf=struct_bf: slip.struct_id == struct_bf)
        self.assertEqual(
            len(slips), 2, "There must be two payslips with Base + Finiquito. Maybe the struct was not changed"
        )
        slip = slips[0]
        self.assertTrue(
            slip.line_ids.filtered(lambda line: line.name == "ISN Finiquito"),
            "The payslip lines of salario + finiquito were not computed",
        )
        payslip = payslip_run.slip_ids - slips
        self.assertEqual(payslip.struct_id, self.struct, "There should be a payslip with the regular Nomina")

        # Test if the option is off
        self.env.company.sudo().write({"l10n_mx_edi_automatic_settlement": False})
        payslip_run = self.payslip_run_obj.create(
            {
                "name": "Payslip VX 2",
                "date_start": "%s-%s-01" % (time.strftime("%Y"), time.strftime("%m")),
                "date_end": "%s-%s-15" % (time.strftime("%Y"), time.strftime("%m")),
                "l10n_mx_edi_payment_date": "%s-%s-15" % (time.strftime("%Y"), time.strftime("%m")),
            }
        )
        self.wizard_batch.create(
            {
                "employee_ids": [Command.set(employees.ids)],
                "structure_id": self.struct.id,
            }
        ).with_context(active_id=payslip_run.id).compute_sheet()
        slips = payslip_run.slip_ids.filtered(lambda slip, struct=struct_bf: slip.struct_id == struct)
        self.assertFalse(slips, "There should be not nómina + finiquito payslips")

    def test_032_daily_payment(self):
        """Check daily wage is correctly calculated"""
        self.assertTrue(
            float_is_zero(self.contract.l10n_mx_edi_daily_wage - self.contract.wage / 30.0, precision_digits=4),
            "The amount in the contract is different that expected.",
        )
        self.contract.company_id.sudo().l10n_mx_edi_days_daily_wage = 30.4
        self.assertTrue(
            float_is_zero(self.contract.l10n_mx_edi_daily_wage - self.contract.wage / 30.4, precision_digits=4),
            "The amount in the contract is different that expected.",
        )

    def test_033_company_loan_net_salary(self):
        """Test if a company loan is greater than the net salary, the payslip line should be cancelled
        and the loan should not have the payslip added"""
        self.employee.loan_ids.write({"active": False})
        company_rule = self.env.ref("l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_deduction_004_loan_company")

        payroll = self.create_payroll()
        payroll.compute_sheet()
        original_net_salary = payroll.net_wage
        self.assertTrue(original_net_salary, "There should be a net salary line")

        # Loan amount is greater
        company_loan = self.env.ref("l10n_mx_edi_payslip.infonavit_qdp")
        company_loan.write(
            {
                "active": True,
                "amount": original_net_salary + 1000,
                "input_type_id": self.env.ref(
                    "l10n_mx_edi_payslip.hr_payslip_input_type_deduction_004_loan_company"
                ).id,
            }
        )
        payroll.compute_sheet()
        loan_line = payroll.line_ids.filtered(lambda line: line.salary_rule_id == company_rule)
        self.assertFalse(loan_line, "There should not be a company loan line in the payslip")
        self.assertEqual(payroll.net_wage, original_net_salary, "The Net salary should not change")
        payroll.action_payslip_done()
        self.assertFalse(company_loan.payslip_ids, "The loan should not have any payslip linked")
        # Loan amount is ok
        second_payroll = self.create_payroll()
        company_loan.write({"amount": 1})
        second_payroll.compute_sheet()
        self.assertTrue(
            second_payroll.line_ids.filtered(lambda line: line.salary_rule_id == company_rule),
            "There should be a company loan line in the payslip",
        )
        second_payroll.action_payslip_done()
        self.assertEqual(len(company_loan.payslip_ids), 1, "There should be one payslip linked to the loan")

    @unittest.skip("Blocking un-mocked external HTTP request")
    def test_034_extra_hours(self):
        """Test if the extra hours salary rules are being calculated with the three rules from ART 93 from ISR law
        1. If the employee has the general minimal salary, 9 hours extra hours by week are exempt
        2. If the employee salary is greater than minimal salary, 50% of the amount is exempt and 50% is taxed
        3. The 50% taxed has as limit of 5 umas, the rest is taxed. for example, if uma = 100 and the total amount
        for extra hours is 1500. Exempt value is 500 and taxed value is 1000.
        """
        extra_exempt_rule = self.env.ref("l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_perception_019_e")
        extra_taxed_rule = self.env.ref("l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_perception_019_g")
        payroll = self.create_payroll()

        # Getting Date for overtime, next monday
        overtime_date = date.today().replace(day=1)
        while overtime_date.weekday():
            overtime_date += timedelta(days=1)
        # The employee's salary is more than minimal salary
        overtimes = self.env["hr.payslip.overtime"].create(
            {
                "employee_id": self.employee.id,
                "name": overtime_date,
                "hours": 3,
            }
        )
        payroll.compute_sheet()
        # The quantity exempt is less than 5 umas
        extra_taxed_line = self.search_rule_in_payroll(payroll, extra_taxed_rule, True)
        extra_exempt_line = self.search_rule_in_payroll(payroll, extra_exempt_rule, True)
        self.assertEqual(
            extra_taxed_line.total, extra_exempt_line.total, "The extra hours amounts should be 50%% exempt 50%% taxed"
        )
        # The exempt amount should be limited to 5 umas
        overtimes += self.env["hr.payslip.overtime"].create(
            {
                "employee_id": self.employee.id,
                "name": overtime_date + timedelta(days=1),
                "hours": 3,
            }
        )
        payroll.compute_sheet()
        extra_taxed_line = self.search_rule_in_payroll(payroll, extra_taxed_rule, True)
        extra_exempt_line = self.search_rule_in_payroll(payroll, extra_exempt_rule, True)
        self.assertTrue(
            extra_taxed_line.total != extra_exempt_line.total,
            "The extra hours amounts should not be 50%% exempt 50%% taxed",
        )
        umas = round(self.contract.company_id.l10n_mx_edi_uma * 5, 2)
        self.assertEqual(extra_exempt_line.total, umas, "The amount in the exempt should be 5 umas")
        taxed_expected = (self.contract.wage / 30.0 / 8 * 2 * sum(overtimes.mapped("hours"))) - umas
        self.assertTrue(
            float_is_zero(extra_taxed_line.total - taxed_expected, precision_digits=2),
            "The amount in the taxed it is not complete",
        )
        # Days with 4 or more days, Triple hours
        overtimes.write({"hours": 4})
        payroll.compute_sheet()
        extra_triple_rule = self.env.ref("l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_perception_019_t")
        extra_triple_line = self.search_rule_in_payroll(payroll, extra_triple_rule, True)
        self.assertTrue(extra_triple_line, "A extra hours triple line should be created, overtimes has more than 3h")
        self.assertTrue(
            float_is_zero(extra_triple_line.total - (self.contract.wage / 30.0 / 8 * 3 * 2), precision_digits=2),
            "The amount in the taxed it is not complete",
        )
        # The salary is the minimal, up to 9 hours are exempt
        overtimes.write({"hours": 3})
        self.contract.wage = self.contract.company_id.l10n_mx_edi_minimum_wage * 30
        payroll.compute_sheet()
        extra_taxed_line = self.search_rule_in_payroll(payroll, extra_taxed_rule)
        self.assertFalse(extra_taxed_line, "Should not be any extra hour taxed line")
        extra_exempt_line = self.search_rule_in_payroll(payroll, extra_exempt_rule, True)
        amount_expected = self.contract.wage / 30.0 / 8 * 2 * sum(overtimes.mapped("hours"))
        self.assertTrue(
            float_is_zero(round(extra_exempt_line.total, 1) - round(amount_expected, 1), precision_digits=4),
            "The extra hours amount expected is %d (Found: %d)" % (amount_expected, round(extra_exempt_line.total, 2)),
        )

        # Check if the overtime node can be added to the cfdi and can be printed
        payroll.action_payslip_done()
        payroll.with_context(payslip_generate_pdf=True).action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)
        xml = payroll.l10n_mx_edi_get_xml_etree()
        node_payroll = payroll.l10n_mx_edi_get_payroll_etree(xml)
        extra_hours_node = [
            p.HorasExtra for p in node_payroll.Percepciones.Percepcion if p.get("TipoPercepcion", "") == "019"
        ]
        self.assertTrue(extra_hours_node, "Extra hours node were not created")

    def test_035_isr_audit(self):
        """Test if the amounts of ISR given by the ISR audit wizard are correct and consistent with the payslip
        Use with two fortnightly to check if the monthly ISR is being adjusting"""
        # Test most common case
        payroll = self.create_payroll()
        payroll.action_refresh_from_work_entries()
        payroll.action_payslip_done()
        audit = self.env["hr.payslip.audit.isr"].with_context(active_ids=payroll.id).create({"payslip_id": payroll.id})
        rule = self.env.ref("l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_deduction_002")
        isr_line = self.search_rule_in_payroll(payroll, rule, True)
        self.assertTrue(
            float_is_zero(isr_line.total - audit.isr, precision_digits=2),
            "The ISR audit wizard should give the same ISR amount than the payslip",
        )
        # Second Fortnightly: Monthly Adjustment
        date_from = payroll.date_to + timedelta(days=1)
        date_to = self.last_day_of_month(date_from)
        second_payroll = self.create_payroll(date_from, date_to)
        second_payroll.action_refresh_from_work_entries()
        second_isr_line = self.search_rule_in_payroll(second_payroll, rule, True)
        second_audit = (
            self.env["hr.payslip.audit.isr"]
            .with_context(active_ids=second_payroll.id)
            .create({"payslip_id": second_payroll.id})
        )
        self.assertTrue(second_audit.previous_isr, "This is a monthly audit, must generate previous isr")
        self.assertTrue(second_audit.monthly_isr, "This is a monthly audit, must generate monthly isr")
        self.assertEqual(
            second_isr_line.total,
            second_audit.isr,
            "The ISR audit wizard should give the same ISR amount than the payslip",
        )
        self.assertTrue(
            float_is_zero(second_audit.monthly_isr - isr_line.total - second_isr_line.total, precision_digits=2),
            "The sum of ISR amounts in the payslips should match with the monthly ISR in the audit",
        )

    @unittest.skip("Audit ISR must be improved")
    def test_036_isr_audit_subsidy(self):
        """Test the subsidy calculation of ISR audit when the payslip was employment subsidy, check if the final ISR
        is being affected in the same way"""
        self.contract.wage = 5000
        payroll = self.create_payroll()
        payroll.action_refresh_from_work_entries()
        subsidy_rule = self.env.ref("l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_other_payment_aux_002")
        subsidy_line = self.search_rule_in_payroll(payroll, subsidy_rule, True)
        audit = self.env["hr.payslip.audit.isr"].with_context(active_ids=payroll.id).create({"payslip_id": payroll.id})
        self.assertEqual(
            round(subsidy_line.total, 2),
            round(audit.subsidy, 2),
            "The Subsidy in audit wizard should give the same amount than the payslip",
        )
        rule = self.env.ref("l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_deduction_002")
        isr_line = self.search_rule_in_payroll(payroll, rule, False)
        self.assertEqual(
            isr_line.total if isr_line else 0,
            audit.isr,
            "The ISR audit wizard should give the same ISR amount than the payslip",
        )

    def test_037_accumulative_aguinaldo(self):
        """Test a case for accumulative aguinaldo, all new aguinaldo part is taxed.
        Case 1. Use the manual input specify acumulated not in odoo
        Case 2. Accumulative aguinaldo from odoo's payslips
        """
        self.contract.date_start = date(2021, 7, 1)
        self.contract.date_end = date(2021, 9, 30)
        self.contract.state = "open"
        self.contract.sudo().company_id.l10n_mx_edi_uma = 89.62
        self.contract.wage = 430.68 * self.contract.company_id.l10n_mx_edi_days_daily_wage
        self.struct = self.env.ref("l10n_mx_edi_payslip.payroll_structure_data_06")
        payroll = self.create_payroll(date(2021, 9, 16), date(2021, 9, 30))
        payroll.compute_sheet()
        exempt_rule = self.env.ref("l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_perception_023_e_3_bf")
        line = self.search_rule_in_payroll(payroll, exempt_rule, True)
        expected_amount = line.total
        payroll.write(
            {
                "input_line_ids": [
                    Command.create(
                        {
                            "amount": 3203.55,
                            "input_type_id": self.ref(
                                "l10n_mx_edi_payslip.hr_payslip_input_type_perception_023_e_3_bf"
                            ),
                        },
                    )
                ],
            }
        )
        payroll.compute_sheet()
        line = self.search_rule_in_payroll(payroll, exempt_rule, False)
        self.assertFalse(line, "There should not be exempt part")
        taxed_rule = self.env.ref("l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_perception_023_g_3_bf")
        line = self.search_rule_in_payroll(payroll, taxed_rule, False)
        self.assertTrue(line, "There should be an aguinaldo proporcional taxed line")
        self.assertEqual(
            line.total,
            expected_amount,
            "All the aguinaldo amount now should be taxed and must be the proporcional for this time",
        )
        payroll.action_payslip_done()
        # Case 2
        self.contract.date_end = date(2021, 11, 30)
        self.struct = self.env.ref("l10n_mx_edi_payslip.payroll_structure_data_06")
        payroll = self.create_payroll(date(2021, 11, 16), date(2021, 11, 30))
        payroll.compute_sheet()
        lines = self.search_rule_in_payroll(payroll, exempt_rule)
        self.assertTrue(
            lines.total < self.contract.sudo().company_id.l10n_mx_edi_uma * 15,
            "The exempt amount should be less than the limit, because there are already a "
            "proportional aguinaldo given in the case 1. Total: %s != expected: %s"
            % (lines.total, self.contract.sudo().company_id.l10n_mx_edi_uma * 15),
        )
        # Case 1 and 2, in just one calculation
        lines |= self.search_rule_in_payroll(payroll, taxed_rule, False)
        self.assertEqual(len(lines), 2, "there should be two lines for aguinaldo, taxed and exempt")
        # The amount gotten here in two lines, now should be given just in taxed
        expected_amount = round(sum(lines.mapped("total")), 2)
        payroll.write(
            {
                "input_line_ids": [
                    Command.create(
                        {
                            "amount": 3203.55,
                            "input_type_id": self.ref(
                                "l10n_mx_edi_payslip.hr_payslip_input_type_perception_023_e_3_bf"
                            ),
                        },
                    )
                ],
            }
        )
        payroll.compute_sheet()
        line = self.search_rule_in_payroll(payroll, exempt_rule, False)
        self.assertFalse(line, "There should not be exempt part")
        line = self.search_rule_in_payroll(payroll, taxed_rule, False)
        self.assertTrue(line, "There should be an aguinaldo proporcional taxed line")
        self.assertEqual(
            line.total,
            expected_amount,
            "All the aguinaldo amount now should be taxed and must be the proporcional for this time",
        )

    def test_038_leave_calendar_days(self):
        """Test the leaves marked as calendar days. This type of leaves should affect the worked days section
        of the payslips. If a leave is register between days that the employee is not working the worked days should
        count those days, again, even if employee does not work those days.
        Actual test case:
        1. Set Timezone: to ensure the timezone is not affecting the last change with leave's dates
        2. Get a leave covering the whole week, the employee does not work Saturdays and sundays so the function
           calendar days should give those days with leaves, even if the employee does not work
        3. A calendar day's leave with 7 days should be created. Normally odoo will give just 5 days
           (the work entries still work that way)
        4. In the payslip should be 7 days of the leave's type.
        """
        self.employee.tz = self.contract.resource_calendar_id.tz = self.env.user.tz
        self.contract.state = "open"
        payroll = self.create_payroll()
        self.remove_leaves()
        leave_type = self.env.ref("l10n_mx_edi_payslip.mexican_riesgo_de_trabajo")
        leave = self.env["hr.leave"].create(
            {
                "holiday_type": "employee",
                "employee_id": self.employee.id,
                "holiday_status_id": leave_type.id,
                "request_date_from": payroll.date_from,
                "request_date_to": payroll.date_from + timedelta(days=6),
            }
        )
        # TODO: Review: This regenerate work entries should not be needed, maybe a odoo's ticket is needed
        self.regenerate_work_entries()
        leave._compute_date_from_to()
        leave.action_approve()
        self.assertEqual(
            leave.number_of_days,
            7.0,
            "The leave is a calendar days leave, 7 days are expected. Even if the employee does not work",
        )
        payroll.action_refresh_from_work_entries()
        absence_line = payroll.worked_days_line_ids.filtered(
            lambda line: line.work_entry_type_id == leave_type.work_entry_type_id
        )
        self.assertTrue(absence_line, "A %s line should be worked days" % leave.name)
        self.assertEqual(
            absence_line.number_of_days,
            leave.number_of_days,
            "The absence days in the payslip should be the same that those in calendar days leaves",
        )

    def test_039_action_open_overtimes(self):
        """Test the action open overtimes, it shows the overtimes corresponding to the weeks in the payslip period"""
        payroll = self.create_payroll()
        action_result = payroll.action_open_overtimes()
        self.assertTrue(isinstance(action_result, dict))
        weeks = set(action_result["domain"][1][2])
        self.assertTrue(payroll.date_from.isocalendar()[1] in weeks, "Wrong weeks in the payslips overtimes view")
        self.assertTrue(
            (payroll.date_from + timedelta(days=8)).isocalendar()[1] in weeks,
            "Wrong weeks in the payslips overtimes view",
        )
        self.assertTrue(payroll.date_to.isocalendar()[1] in weeks, "Wrong weeks in the payslips overtimes view")

    @unittest.skip("Blocking un-mocked external HTTP request")
    def test_040_solfact_sign_cancel(self):
        """Test the sign process using solfact as PAC, simple sign and cancel"""
        self.env.company.sudo().l10n_mx_edi_pac = "solfact"
        self.env.company.sudo().l10n_mx_edi_pac_test_env = True
        payroll = self.create_payroll()
        # Check Error that solfact returns and finkok not. El nodo Nomina.Emisor.EntidadSNCF no debe existir.
        payroll.l10n_mx_edi_source_resource = False
        payroll.compute_sheet()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)
        # TODO: Cancel for Solfact is pending
        # payroll.l10n_mx_edi_cancellation = '03'
        # payroll.l10n_mx_edi_action_request_edi_cancel()
        # payroll.l10n_mx_edi_update_pac_status()
        # self.assertTrue(payroll.l10n_mx_edi_pac_status in ('to_cancel', 'cancelled'), payroll.l10n_mx_edi_error)

    def test_041_unpaid_leave_as_deduction(self):
        payroll = self.create_payroll()
        self.assertEqual(
            len(payroll.worked_days_line_ids),
            1,
            "The worked days are expected to be just 1 type, "
            "attendances, please update this Test if is not anymore",
        )
        payroll.worked_days_line_ids.number_of_days -= 3
        payroll.write(
            {
                "worked_days_line_ids": [
                    Command.create(
                        {
                            "name": "Falta justificada sin goce de salario",
                            "code": "LEAVE114",
                            "number_of_days": 1,
                            "number_of_hours": 8,
                            "contract_id": self.contract.id,
                            "work_entry_type_id": self.ref(
                                "l10n_mx_edi_payslip.work_entry_type_mexican_faltas_injustificadas"
                            ),
                        },
                    ),
                    Command.create(
                        {
                            "name": "Licencia sin goce de salario",
                            "code": "LEAVE115",
                            "number_of_days": 1,
                            "number_of_hours": 8,
                            "contract_id": self.contract.id,
                            "work_entry_type_id": self.ref(
                                "l10n_mx_edi_payslip.work_entry_type_mexican_licencia_sin_goce"
                            ),
                        },
                    ),
                    Command.create(
                        {
                            "name": "Ausentismo",
                            "code": "LEAVE90",
                            "number_of_days": 1,
                            "number_of_hours": 8,
                            "contract_id": self.contract.id,
                            "work_entry_type_id": self.ref("hr_work_entry_contract.work_entry_type_unpaid_leave"),
                        },
                    ),
                ],
            }
        )
        payroll.contract_id.sudo().company_id.l10n_mx_edi_use_leave_deduction = False
        payroll.compute_sheet()
        line = payroll.line_ids.filtered(lambda line: line.code == "FJSS" and line.category_id.code == "AUX")
        self.assertTrue(
            line,
            "There should be a line with the code FJSS: Falta Justificada Sin Goce de Salario and "
            "with type auxiliar",
        )
        original_net_salary = payroll.net_wage
        payroll.contract_id.sudo().company_id.l10n_mx_edi_use_leave_deduction = True
        payroll.compute_sheet()
        line = payroll.line_ids.filtered(lambda line: line.code == "FJSS" and line.category_id.code == "DED")
        self.assertTrue(
            line,
            "There should be a line with the code FJSS: Falta Justificada Sin Goce de Salario and Type Deduction",
        )
        self.assertEqual(original_net_salary, payroll.net_wage, "The net salary of both options should be the same")

    def test_043_disciplinary_warning(self):
        self.employee.sudo().l10n_mx_edi_disciplinary_warning_ids = [
            Command.create(
                {
                    "name": "Disciplinary Warning",
                    "date": date.today(),
                    "company_id": self.employee.company_id.id,
                    "notes": "<p>Disciplinary Warning</p>",
                },
            ),
            Command.create(
                {
                    "name": "Disciplinary Warning 2",
                    "date": date.today(),
                    "company_id": self.employee.company_id.id,
                    "notes": "<p>Disciplinary Warning 2</p>",
                },
            ),
        ]
        self.env["hr.employee.disciplinary.warning"].create(
            {
                "name": "Disciplinary Warning 3",
                "employee_id": self.employee.id,
                "date": date.today(),
                "company_id": self.employee.company_id.id,
                "notes": "<p>Disciplinary Warning 3</p>",
            }
        )
        self.assertEqual(
            self.employee.l10n_mx_edi_disciplinary_warning_count,
            3,
            "Three disciplinary warnings are expected in the count.",
        )

    def _check_out_of_contract_config(self, payroll, expected_out_of_contract_days, expected_lines=2):
        total_period_days = (payroll.date_to - payroll.date_from).days + 1
        payroll.action_refresh_from_work_entries()
        worked_lines = payroll.worked_days_line_ids
        self.assertEqual(len(worked_lines), expected_lines, "%d Lines expected" % expected_lines)
        self.assertEqual(
            sum(worked_lines.mapped("number_of_days")),
            total_period_days,
            "The total sum of number of days must be the total of days in the period, %d days" % total_period_days,
        )
        self.assertTrue(
            len(worked_lines.mapped("name")) == len(set(worked_lines.mapped("name"))),
            "No concept should be repeated in worked days lines",
        )
        self.assertFalse(
            [item for item in worked_lines.mapped("number_of_days") if item < 1],
            "There should be no lines with negative or zero days in the worked days",
        )
        out_contract_line = worked_lines.filtered(lambda w: w.name == "Out of Contract")
        self.assertTrue(out_contract_line, "There must be an Out of Contract line")
        self.assertEqual(
            out_contract_line.number_of_days,
            expected_out_of_contract_days,
            "There must be %s days out of contract" % expected_out_of_contract_days,
        )

    @unittest.skip("Blocking un-mocked external HTTP request")
    def test_base_finiquito(self):
        """Ensure that structure base + finiquito is executed correctly."""
        self.struct = self.env.ref("l10n_mx_edi_payslip.payroll_structure_data_06")
        payroll = self.create_payroll()
        date_start = payroll.l10n_mx_edi_payment_date - timedelta(days=380)
        self.contract.write(
            {
                "date_start": date_start,
            }
        )
        payroll.compute_sheet()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)

    @unittest.skip("Blocking un-mocked external HTTP request")
    def test_base_viaticos(self):
        """Ensure that structure for viaticos is executed correctly."""
        self.struct = self.env.ref("l10n_mx_edi_payslip.payroll_structure_data_07")
        payroll = self.create_payroll()
        payroll.input_line_ids[-1].input_type_id = self.ref(
            "l10n_mx_edi_payslip.hr_payslip_input_type_other_payment_003"
        )
        payroll.compute_sheet()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)

    @unittest.skip("Blocking un-mocked external HTTP request")
    def test_base_week(self):
        """Ensure that structure base is executed correctly for week."""
        payroll = self.create_payroll()
        self.contract.l10n_mx_edi_schedule_pay_id = self.env.ref("l10n_mx_edi_payslip.schedule_pay_weekly")
        payroll.date_to = payroll.date_from + timedelta(days=7)
        payroll.compute_sheet()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)

    def test_net_salary_in_0(self):
        """Ensure that not try to stamp when net salary is 0"""
        payroll = self.create_payroll()
        payroll.input_line_ids.unlink()
        self.contract.wage = 0
        payroll.employee_id.sudo().l10n_mx_edi_is_assimilated = True
        payroll.employee_id.loan_ids.action_close()
        payroll.compute_sheet()
        payroll.action_payslip_done()
        self.assertFalse(payroll.l10n_mx_edi_pac_status, payroll.l10n_mx_edi_error)

    @unittest.skip("Blocking un-mocked external HTTP request")
    def test_xml_subsidy(self):
        """Ensure that payroll is signed with subsidy"""
        self.employee.sudo().contract_id = self.contract
        self.contract.wage = 4000.00
        payroll = self.create_payroll()
        payroll.compute_sheet()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)

    @unittest.skip("Blocking un-mocked external HTTP request")
    def test_prorrate_isr(self):
        """Ensure that rules with l10n_mx_edi_prorate_isr works correctly"""
        payroll = self.create_payroll()
        payroll.company_id.sudo().l10n_mx_edi_prorate_isr = True
        payroll.compute_sheet()
        payroll.action_payslip_done()
        payroll.l10n_mx_edi_update_pac_status()
        self.assertEqual(payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)

    def test_leave_without_salary(self):
        """Ensure that leave for 'Falta Justificada Sin Goce de Salario' is created"""
        holiday = self.env.ref("l10n_mx_edi_payslip.work_entry_type_mexican_faltas_injustificadas").id
        self.employee.parent_id = False
        allocation = self.env["hr.leave.allocation"].create(
            {
                "name": "Test",
                "holiday_status_id": holiday,
                "number_of_days": 10,
                "holiday_type": "employee",
                "employee_id": self.employee.id,
                "state": "confirm",
            }
        )
        allocation.sudo().action_validate()
        self.remove_leaves()
        leave = self.env["hr.leave"].create(
            {
                "holiday_type": "employee",
                "employee_id": self.employee.id,
                "holiday_status_id": holiday,
                "request_date_from": "%s-%s-01" % (time.strftime("%Y"), time.strftime("%m")),
                "request_date_to": "%s-%s-03" % (time.strftime("%Y"), time.strftime("%m")),
                "number_of_days": 3,
            }
        )
        leave._compute_date_from_to()
        leave.action_approve()
        payroll = self.create_payroll()
        payroll.action_refresh_from_work_entries()
        payroll.action_payslip_done()

        # Base + finiquito
        self.struct = self.env.ref("l10n_mx_edi_payslip.payroll_structure_data_06")
        payroll = self.create_payroll()
        payroll.action_refresh_from_work_entries()
        payroll.action_payslip_done()

    def test_not_attendance(self):
        """Ensure that not attendance is considered in the salary"""
        payroll = self.env.ref("l10n_mx_edi_payslip.hr_payslip_mlc_cfdi0")
        payroll.contract_id.state = "open"
        payroll.employee_id.l10n_mx_edi_force_attendances = True
        self.generate_attendances(self.employee, payroll.date_from, payroll.date_to - timedelta(days=3))
        payroll.action_refresh_from_work_entries()
        self.assertTrue(
            payroll.worked_days_line_ids.filtered(lambda line: line.code == "LEAVE150"),
            "Not attendance not in payslip.",
        )

        payroll.employee_id.attendance_ids.unlink()
        self.remove_leaves()
        leave = self.env["hr.leave"].create(
            {
                "holiday_type": "employee",
                "employee_id": self.employee.id,
                "holiday_status_id": self.env.ref("l10n_mx_edi_payslip.mexican_licencia_padres_hijo_cancer").id,
                "request_date_from": "%s-%s-01" % (time.strftime("%Y"), time.strftime("%m")),
                "request_date_to": "%s-%s-03" % (time.strftime("%Y"), time.strftime("%m")),
                "number_of_days": 3,
            }
        )
        leave._compute_date_from_to()
        leave.action_approve()
        self.generate_attendances(
            self.employee, payroll.date_from + timedelta(days=3), payroll.date_to + timedelta(days=1)
        )
        payroll.action_refresh_from_work_entries()
        self.assertFalse(
            payroll.worked_days_line_ids.filtered(lambda line: line.code == "LEAVE150"), "Not attendance in payslip."
        )

    def generate_attendances(self, employee, date_from, date_to):
        for day in range((date_to - date_from).days):
            dt_from = date_from + timedelta(days=day)
            self.env["hr.attendance"].create(
                {
                    "employee_id": employee.id,
                    "check_in": datetime.combine(dt_from, dt_time(12, 0)),
                    "check_out": datetime.combine(dt_from, dt_time(23, 59, 59)),
                }
            )

    def test_infornavit_loan_period(self):
        """Ensure that loans from infonavit are not over-charged when the
        loan period does not coincide with the psyslip period"""
        payroll = self.create_payroll()
        # setting up loan
        loan = self.env.ref("l10n_mx_edi_payslip.infonavit_qdp")
        loan.amount = 10000
        loan.infonavit_type = "fixed_amount"
        loan.date_from = payroll.date_from
        loan.date_to = loan.date_from + timedelta(days=9)
        # compute sheet
        payroll.compute_sheet()
        # setting up expected amount
        line = payroll.line_ids.filtered(lambda line: line.code == "INF009")
        date_payroll = payroll.date_from
        leap_year = not date_payroll.year % 4 and date_payroll.year % 100 or not date_payroll.year % 400
        period = {1: 59 if not leap_year else 60, 2: 59 if not leap_year else 60, 7: 62, 8: 62}
        expected_amount = float_round(loan.amount * 2 / period.get(date_payroll.month, 61) * 10, precision_digits=2)
        # tests
        self.assertEqual(line.total, expected_amount, "Loan charge not calculated correctly for the period")

    def test_liquidacion_structure(self):
        """Ensure that liquidacion is generated correctly."""
        self.struct = self.env.ref("l10n_mx_edi_payslip.payroll_structure_data_04")
        payroll = self.create_payroll()
        payroll.compute_sheet()
        payroll.action_payslip_done()
        # TODO: Enable with mock
        # payroll.l10n_mx_edi_update_pac_status()
        # self.assertEqual(payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)

    def test_ptu_structure(self):
        """Ensure that PTU is generated correctly."""
        self.struct = self.env.ref("l10n_mx_edi_payslip.payroll_structure_data_05")
        payroll = self.create_payroll()
        payroll.input_line_ids[0].write(
            {
                "amount": 20000.0,
                "input_type_id": self.ref("l10n_mx_edi_payslip.hr_payslip_input_type_perception_003_g"),
            }
        )
        payroll.compute_sheet()
        payroll.action_payslip_done()
        # TODO: Enable with mock
        # payroll.l10n_mx_edi_update_pac_status()
        # self.assertEqual(payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error)
