import os
import time
from datetime import timedelta
from os.path import join

from lxml import objectify

from odoo import Command
from odoo.tests.common import TransactionCase


class L10nMxEdiPayslipTransactionCase(TransactionCase):
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
        self.contract.l10n_mx_edi_schedule_pay_id = self.env.ref("l10n_mx_edi_payslip.schedule_pay_fortnightly")
        self.contract.action_update_current_holidays()
        self.contract._compute_integrated_salary()
        self.contract.compute_integrated_salary_variable()
        self.struct = self.env.ref("l10n_mx_edi_payslip.payroll_structure_data_01")
        self.cat_excempt = self.env.ref("l10n_mx_edi_payslip.hr_salary_rule_category_perception_mx_exempt")
        self.company = self.env.company

        xml_expected_path = join(os.path.dirname(os.path.realpath(__file__)), "expected_cfdi.xml")
        with open(xml_expected_path) as xml_expected_f:
            self.xml_expected = objectify.parse(xml_expected_f).getroot()
        self.partnerc = self.company.partner_id
        journal = (
            self.env["account.journal"]
            .sudo()
            .search([("type", "=", "general"), ("company_id", "=", self.company.id)], limit=1)
        )
        journal.default_account_id = self.env.ref("l10n_mx_edi_payslip.cuenta601_08")
        self.struct.journal_id = journal
        self.env.ref("l10n_mx_edi_payslip.payroll_structure_data_02").journal_id = journal
        self.env.ref("l10n_mx_edi_payslip.payroll_structure_data_03").journal_id = journal
        self.env.ref("l10n_mx_edi_payslip.payroll_structure_data_06").journal_id = journal

    def create_payroll(self, date_from=None, date_to=None):
        return self.payslip_obj.create(
            {
                "name": "Payslip Test",
                "employee_id": self.employee.id,
                "contract_id": self.contract.id,
                "struct_id": self.struct.id,
                "date_from": date_from or "%s-%s-01" % (time.strftime("%Y"), time.strftime("%m")),
                "date_to": date_to or "%s-%s-15" % (time.strftime("%Y"), time.strftime("%m")),
                "l10n_mx_edi_source_resource": "IP",
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
                "input_line_ids": [
                    Command.create(
                        {
                            "amount": 200.0,
                            "contract_id": self.contract.id,
                            "input_type_id": self.ref("l10n_mx_edi_payslip.hr_payslip_input_type_perception_005_e"),
                        },
                    ),
                    Command.create(
                        {
                            "amount": 1,
                            "contract_id": self.contract.id,
                            "input_type_id": self.ref("l10n_mx_edi_payslip.hr_payslip_input_type_perception_047_e"),
                        },
                    ),
                    Command.create(
                        {
                            "amount": 300.0,
                            "contract_id": self.contract.id,
                            "input_type_id": self.ref("l10n_mx_edi_payslip.hr_payslip_input_type_other_payment_003"),
                        },
                    ),
                ],
            }
        )

    def remove_leaves(self):
        leaves = self.env["hr.leave"].search([("employee_id", "=", self.employee.id)])
        leaves.filtered(lambda line: line.state == "validate").action_refuse()
        leaves.sudo().action_draft()
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
            {"company_id": self.company.id, "code": "%s.%s" % (account.code, second_employee.id)}
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
                                    "account_src_id": self.env.ref("l10n_mx_edi_payslip.cuenta601_08").id,
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
        lines = payroll.line_ids.filtered(lambda line: line.salary_rule_id == salary_rule_id)
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
            return (element.tag, dict(map(recursive_dict, element.getchildren()), **element.attrib))

        return dict([recursive_dict(xml)])

    def regenerate_work_entries(self, employee=None, contract=None, date_from=None, date_to=None):
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

    # pylint: disable=invalid-name
    def assertEqualXML(self, xml_real, xml_expected):
        """Receive 2 objectify objects and show a diff assert if exists."""
        xml_expected = self.xml2dict(xml_expected)
        xml_real = self.xml2dict(xml_real)
        # noqa "self.maxDiff = None" is used to get a full diff from assertEqual method
        # This allow us get a precise and large log message of where is failing
        # expected xml vs real xml More info:
        # noqa https://docs.python.org/2/library/unittest.html#unittest.TestCase.maxDiff
        self.maxDiff = None
        self.assertEqual(xml_real, xml_expected)
