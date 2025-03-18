import os
import time
from contextlib import contextmanager
from datetime import timedelta
from os.path import join
from unittest.mock import patch

from lxml import etree, objectify

from odoo import Command

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class L10nMxEdiPayslipTransactionCase(AccountTestInvoicingCommon):
    def setUp(self):
        super().setUp()
        self.uid = self.env.ref("l10n_mx_edi_payslip.payroll_mx_manager")
        self.payslip_obj = self.env["hr.payslip"]
        self.allocation_obj = self.env["hr.leave.allocation"]
        self.mail_obj = self.env["mail.compose.message"]
        self.payslip_run_obj = self.env["hr.payslip.run"]
        self.wizard_batch = self.env["hr.payslip.employees"]
        self.employee = self.env.ref("l10n_mx_edi_payslip.mx_employee_qdp")
        self.contract = self.env.ref("l10n_mx_edi_payslip.hr_contract_maria").sudo()
        self.contract.l10n_mx_edi_schedule_pay_id = self.env.ref(
            "l10n_mx_edi_payslip.schedule_pay_fortnightly"
        )
        self.contract.action_update_current_holidays()
        self.contract._compute_integrated_salary()
        self.contract.compute_integrated_salary_variable()
        self.struct = self.env.ref("l10n_mx_edi_payslip.payroll_structure_data_01")
        self.cat_excempt = self.env.ref(
            "l10n_mx_edi_payslip.hr_salary_rule_category_perception_mx_exempt"
        )
        self.company = self.env.company

        xml_expected_path = join(
            os.path.dirname(os.path.realpath(__file__)), "expected_cfdi.xml"
        )
        with open(xml_expected_path) as xml_expected_f:
            self.xml_expected = objectify.parse(xml_expected_f).getroot()
        self.partnerc = self.company.partner_id
        journal = (
            self.env["account.journal"]
            .sudo()
            .search(
                [("type", "=", "general"), ("company_id", "=", self.company.id)],
                limit=1,
            )
        )
        journal.default_account_id = self.env.ref("l10n_mx_edi_payslip.cuenta601_08")
        self.struct.journal_id = journal
        self.env.ref("l10n_mx_edi_payslip.payroll_structure_data_02").journal_id = (
            journal
        )
        self.env.ref("l10n_mx_edi_payslip.payroll_structure_data_03").journal_id = (
            journal
        )
        self.env.ref("l10n_mx_edi_payslip.payroll_structure_data_06").journal_id = (
            journal
        )

    @contextmanager
    def with_mocked_mx_payslip_pac_sucess(self):
        def fake_l10n_mx_edi_finkok_sign(record, _credentials):
            tree = etree.fromstring(record.l10n_mx_edi_cfdi)
            stamp = """
                <tfd:TimbreFiscalDigital
                    xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
                    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                    xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
                    xsi:schemaLocation="http://www.sat.gob.mx/TimbreFiscalDigital http://www.sat.gob.mx/sitio_internet/cfd/TimbreFiscalDigital/TimbreFiscalDigitalv11.xsd"
                    Version="1.1"
                    UUID="26083EC0-8C43-56FC-B1E9-FF42DA4161BB"
                    FechaTimbrado="___ignore___"
                    NoCertificadoSAT="___ignore___"
                    RfcProvCertif="___ignore___"
                    SelloCFD="___ignore___"
                    SelloSAT="___ignore___"
                />
            """  # noqa
            namespaces = {
                "cfdi": "http://www.sat.gob.mx/cfd/4",
                "nomina12": "http://www.sat.gob.mx/nomina12",
            }
            nomina_nodes = tree.xpath(
                "//cfdi:Complemento/nomina12:Nomina", namespaces=namespaces
            )
            if nomina_nodes:
                nomina_node = nomina_nodes[0]
                timbre_node = etree.fromstring(stamp)
                nomina_node.addnext(timbre_node)
            tree = etree.tostring(tree, xml_declaration=True, encoding="UTF-8")
            record.l10n_mx_edi_pac_status = "signed"
            record.l10n_mx_edi_cfdi = tree

        with patch.object(
            type(self.env["hr.payslip"]),
            "_l10n_mx_edi_finkok_sign",
            fake_l10n_mx_edi_finkok_sign,
        ):
            yield

    @contextmanager
    def with_mocked_mx_payslip_pac_retry(self):
        def fake_l10n_mx_edi_retry(_record):
            _record.l10n_mx_edi_pac_status = "retry"
            _record.l10n_mx_edi_error = "Error during the process: mock test"

        with patch.object(
            type(self.env["hr.payslip"]), "_l10n_mx_edi_retry", fake_l10n_mx_edi_retry
        ):
            yield

    @contextmanager
    def with_mocked_mx_payslip_sat_status_sucess(self):
        def fake_l10n_mx_edi_update_sat_status(_record):
            _record.l10n_mx_edi_sat_status = "not_found"

        with patch.object(
            type(self.env["hr.payslip"]),
            "l10n_mx_edi_update_sat_status",
            fake_l10n_mx_edi_update_sat_status,
        ):
            yield

    def create_payroll(self, date_from=None, date_to=None):
        return self.payslip_obj.create(
            {
                "name": "Payslip Test",
                "employee_id": self.employee.id,
                "contract_id": self.contract.id,
                "struct_id": self.struct.id,
                "date_from": date_from
                or "%s-%s-01" % (time.strftime("%Y"), time.strftime("%m")),
                "date_to": date_to
                or "%s-%s-15" % (time.strftime("%Y"), time.strftime("%m")),
                "l10n_mx_edi_source_resource": "IP",
                "worked_days_line_ids": [
                    Command.create(
                        {
                            "name": "Normal Working Days",
                            "code": "WORK100",
                            "number_of_days": 15,
                            "number_of_hours": 40,
                            "contract_id": self.contract.id,
                            "work_entry_type_id": self.ref(
                                "hr_work_entry.work_entry_type_attendance"
                            ),
                        },
                    )
                ],
                "input_line_ids": [
                    Command.create(
                        {
                            "amount": 200.0,
                            "contract_id": self.contract.id,
                            "input_type_id": self.ref(
                                "l10n_mx_edi_payslip.hr_payslip_input_type_perception_005_e"
                            ),
                        },
                    ),
                    Command.create(
                        {
                            "amount": 1,
                            "contract_id": self.contract.id,
                            "input_type_id": self.ref(
                                "l10n_mx_edi_payslip.hr_payslip_input_type_perception_047_e"
                            ),
                        },
                    ),
                    Command.create(
                        {
                            "amount": 300.0,
                            "contract_id": self.contract.id,
                            "input_type_id": self.ref(
                                "l10n_mx_edi_payslip.hr_payslip_input_type_other_payment_003"
                            ),
                        },
                    ),
                ],
            }
        )

    def remove_leaves(self):
        leaves = self.env["hr.leave"].search([("employee_id", "=", self.employee.id)])
        leaves.filtered(lambda line: line.state == "validate").action_refuse()
        leaves.sudo().action_reset_confirm()
        leaves.unlink()

    def prepare_second_employee(self, fiscal_position=False):
        second_employee = self.employee.sudo().copy()
        contract_second_employee = self.contract.copy(
            {
                "employee_id": second_employee.id,
                "date_generated_from": self.contract.date_generated_from,
                "date_generated_to": self.contract.date_generated_to,
            }
        )
        # This write is executing a needed behavior
        contract_second_employee.write(
            {
                "state": "open",
            }
        )
        # Make sure the second employee has work entries correctly created
        self.regenerate_work_entries(second_employee, contract_second_employee)
        xml_id = f"account.{self.company.id}_cuenta601_84"
        account = self.env.ref(xml_id).sudo()
        account601_84 = account.copy(
            {
                "company_ids": [Command.link(self.company.id)],
                "code": "%s.%s" % (account.code, second_employee.id),
            }
        )
        if fiscal_position:
            department = self.env.ref("hr.dep_rd")
            fiscal_position = (
                self.env["account.fiscal.position"]
                .sudo()
                .create(
                    {
                        "name": "employee test",
                        "account_ids": [
                            Command.create(
                                {
                                    "account_src_id": self.env.ref(
                                        "l10n_mx_edi_payslip.cuenta601_08"
                                    ).id,
                                    "account_dest_id": account601_84.id,
                                },
                            )
                        ],
                    }
                )
            )
            department.property_account_position_id = fiscal_position
            contract_second_employee.department_id = department
        return second_employee

    def search_rule_in_payroll(self, payroll, salary_rule_id, not_found_error=False):
        lines = payroll.line_ids.filtered(
            lambda line: line.salary_rule_id == salary_rule_id
        )
        if not_found_error:
            self.assertTrue(lines, "Expected line %s not found" % salary_rule_id.name)
        return lines

    def last_day_of_month(self, any_day):
        next_month = any_day.replace(day=28) + timedelta(days=4)
        return next_month - timedelta(days=next_month.day)

    def xml2dict(self, xml):
        """Receive 1 lxml etree object and return a dict string.
        This method allow us have a precise diff output"""

        def recursive_dict(element):
            return (
                element.tag,
                dict(map(recursive_dict, element.getchildren()), **element.attrib),
            )

        return dict([recursive_dict(xml)])

    def regenerate_work_entries(
        self, employee=None, contract=None, date_from=None, date_to=None
    ):
        employee = employee or self.employee[0]
        contract = contract or self.contract[0]
        # Make sure contract is active, the write are executing a behavior
        contract.write({"state": "open"})
        # The date_generated_ are the limit dates to generat work entries
        wizard = (
            self.env["hr.work.entry.regeneration.wizard"]
            .sudo()
            .create(
                {
                    "date_from": date_from or self.contract.date_generated_from.date(),
                    "date_to": date_to or self.contract.date_generated_to.date(),
                    "employee_ids": [Command.set(employee.ids)],
                }
            )
        )
        wizard.regenerate_work_entries()

    def check_inability_node(self, payroll, i_type, days):
        """Check if the Incapacidad node was created as expected.
        :param payroll: A payroll object already signed
        :type payroll: hr.payslip
        :param i_type: Inhability type according SAT catalog
        :type i_type: string
        :param days: Expected days in the node. Integer as a string
        :type days: string
        """
        self.assertEqual(
            payroll.l10n_mx_edi_pac_status, "signed", payroll.l10n_mx_edi_error
        )
        xml = payroll.l10n_mx_edi_get_xml_etree()
        self.assertEqual(
            i_type,
            payroll.l10n_mx_edi_get_payroll_etree(xml).Incapacidades.Incapacidad.get(
                "TipoIncapacidad"
            ),
            "Inability not added.",
        )
        self.assertEqual(
            days,
            payroll.l10n_mx_edi_get_payroll_etree(xml).Incapacidades.Incapacidad.get(
                "DiasIncapacidad"
            ),
            "Days in CFDI does not match with the leave.",
        )

    def _check_out_of_contract_config(
        self, payroll, expected_out_of_contract_days, expected_lines=2
    ):
        total_period_days = (payroll.date_to - payroll.date_from).days + 1
        payroll.action_refresh_from_work_entries()
        worked_lines = payroll.worked_days_line_ids
        self.assertEqual(
            len(worked_lines), expected_lines, "%d Lines expected" % expected_lines
        )
        self.assertEqual(
            sum(worked_lines.mapped("number_of_days")),
            total_period_days,
            "The total sum of number of days must be the total of days in the period, %d days"
            % total_period_days,
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
