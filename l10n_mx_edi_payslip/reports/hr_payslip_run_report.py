from collections import defaultdict

from odoo import _, api, models
from odoo.tools import groupby


class RayaListReport(models.AbstractModel):
    _name = "report.l10n_mx_edi_payslip.raya_list_report"
    _description = "Process the data to generate the Raya List Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data if data is not None else {}

        payslip_data = self.env["hr.payslip"].read_group(
            domain=[("payslip_run_id", "in", docids)],
            fields=["payslip_ids:array_agg(id)", "payslip_run_id"],
            groupby=["payslip_run_id", "department_id", "l10n_mx_edi_employer_registration_id"],
            lazy=False,
        )
        batches = defaultdict(lambda: defaultdict(dict))
        department = self.env["hr.department"]

        for row in payslip_data:
            batch_perceptions = []
            batch_deductions = []
            batch_obligations = []
            payslip_run_id = self.env["hr.payslip.run"].browse(row.get("payslip_run_id")[0])
            payslips = self.env["hr.payslip"].browse(row.get("payslip_ids"))
            department_id = row.get("department_id", False)
            department_name = department.browse(department_id[0]).name if department_id else _("Without Department")
            data_perception_deduction = defaultdict(dict)
            employer_registration = row.get("l10n_mx_edi_employer_registration_id")
            employer_registration = (
                self.env["l10n_mx_edi.employer.registration"].browse(employer_registration[0]).name
                if employer_registration
                else payslip_run_id.company_id.company_registry
            )

            for payslip in payslips:
                perceptions = payslip.get_cfdi_perceptions_data()
                deductions = payslip.get_cfdi_deductions_data()
                other_payments = payslip.get_cfdi_other_payments_data()

                total_perceptions = other_payments.get("total_other") + perceptions.get("total_perceptions")
                total_deductions = deductions.get("total_deductions")
                overtimes = self.env["hr.payslip.overtime"].search(
                    [
                        ("employee_id", "=", payslip.employee_id.id),
                        ("name", ">=", payslip.date_from),
                        ("name", "<=", payslip.date_to),
                        ("hours", "!=", 0),
                        ("is_simple", "=", False),
                    ]
                )
                overtimes = sum(overtimes.mapped("hours"))

                data_perception_deduction[payslip] = {
                    "perceptions": perceptions["perceptions"],
                    "total_perceptions": total_perceptions,
                    "total_deductions": total_deductions,
                    "net_to_pay": payslip.net_wage,
                    "deductions": deductions["deductions"],
                    "overtimes": overtimes,
                }
                batch_obligations += payslip.line_ids.filtered(
                    lambda line: line.salary_rule_id.code in ["SSComp", "CesComp"] and line.total
                )
                batch_perceptions += perceptions["perceptions"]
                batch_deductions += deductions["deductions"]

            perceptions_summary = defaultdict(dict)
            deductions_summary = defaultdict(dict)
            obligations_summary = defaultdict(dict)

            total_perceptions = 0
            for salary_rule, lines_in_salary in groupby(batch_perceptions, key=lambda p: p["salary_rule_id"]):
                subtotal = sum(line["total"] for line in list(lines_in_salary))
                perceptions_summary[salary_rule] = subtotal
                total_perceptions += subtotal
            total_deductions = 0
            for salary_rule, lines_in_salary in groupby(batch_deductions, key=lambda p: p["salary_rule_id"]):
                subtotal = sum(line["total"] for line in list(lines_in_salary))
                deductions_summary[salary_rule] = subtotal
                total_deductions += subtotal
            total_obligations = 0
            for salary_rule, lines_in_salary in groupby(batch_obligations, key=lambda p: p["salary_rule_id"]):
                subtotal = sum(line["total"] for line in list(lines_in_salary))
                obligations_summary[salary_rule] = subtotal
                total_obligations += subtotal

            batches[payslip_run_id][department_name][employer_registration] = {
                "perceptions_deductions": data_perception_deduction,
                "deductions_summary": deductions_summary,
                "perceptions_summary": perceptions_summary,
                "total_perceptions": total_perceptions,
                "total_deductions": total_deductions,
                "net_to_pay": total_perceptions - total_deductions,
                "total_employees": len(payslips),
                "total_obligations": total_obligations,
                "obligations_summary": obligations_summary,
            }

        return {
            "batches": batches,
        }
