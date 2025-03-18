from odoo import api, fields, models
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class HrAlimonyReportHandler(models.AbstractModel):
    _name = "hr.alimony.report.handler"
    _description = "Alimony report"
    _inherit = "account.report.custom.handler"

    def _report_custom_engine_alimony_report(
        self,
        expressions,
        options,
        date_scope,
        current_groupby,
        next_groupby,
        offset=0,
        limit=None,
        warnings=None,
    ):
        def build_dict(report, current_groupby, query_res):
            if not current_groupby:
                return (
                    query_res[0]
                    if query_res
                    else {
                        k: None for k in report.mapped("line_ids.expression_ids.label")
                    }
                )
            return [(group_res["grouping_key"], group_res) for group_res in query_res]

        report = self.env["account.report"].browse(options["report_id"])
        # query_res = self._execute_query(report, current_groupby, options, offset, limit)
        query_res = self._get_lines(options)
        return build_dict(report, current_groupby, query_res)

    @api.model
    def _get_report_name(self):
        company = self.env.company
        vat = company.vat or ""
        return self.env._(
            "Alimony_%(vat)s_%(date)s",
            vat=vat,
            date=fields.date.today().strftime("%Y%m"),
        )

    @api.model
    def _get_lines(self, options, line_id=None):
        lines = []
        total_perceptions = total_isr = total_alimony = 0
        date_from = fields.datetime.strptime(
            options["date"]["date_from"], DEFAULT_SERVER_DATE_FORMAT
        ).date()
        date_to = fields.datetime.strptime(
            options["date"]["date_to"], DEFAULT_SERVER_DATE_FORMAT
        ).date()
        slips = self.env["hr.payslip"].search(
            [
                ("state", "=", "done"),
                ("date_from", ">=", date_from),
                ("date_to", "<=", date_to),
            ],
            order="employee_id",
        )
        percep = self.env.ref(
            "l10n_mx_edi_payslip.hr_salary_rule_category_perception_mx_taxed"
        ) | self.env.ref(
            "l10n_mx_edi_payslip.hr_salary_rule_category_perception_mx_exempt"
        )

        alimony_rules = self.env.ref(
            "l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_deduction_007"
        )
        base_ref = "l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_deduction_007%s"
        alimony_refs = [
            "_b",
            "_c",
            "_d",
            "_e",
            "_f",
            "_g",
            "_bf",
            "_b_bf",
            "_c_bf",
            "_d_bf",
            "_e_bf",
            "_f_bf",
            "_g_bf",
            "_a02",
            "_b02",
            "_c02",
        ]

        for alimony_ref in alimony_refs:
            alimony_rules += self.env.ref(base_ref % alimony_ref)

        last_employee = None
        for slip in slips:
            employee = slip.employee_id
            alimony = employee.l10n_mx_edi_alimony_ids.filtered(
                lambda a: a.date_from <= slip.date_from
                and (not a.date_to or a.date_to and a.date_to >= slip.date_to)
            )
            count = 0
            for line in slip.line_ids.filtered(
                lambda line: line.amount and line.salary_rule_id in alimony_rules
            ):
                if employee != last_employee:
                    last_employee = employee
                    lines.append(
                        {
                            "id": employee.id,
                            "name": employee.name,
                            "columns": [{"name": ""} for x in range(8)],
                            "level": 1,
                            "unfoldable": True,
                            "unfolded": True,
                        }
                    )

                line_columns = [
                    {"employee_code": employee.barcode or employee.id},
                    {"vat": employee.l10n_mx_rfc},
                    {
                        "payment_date": fields.datetime.strftime(
                            slip.l10n_mx_edi_payment_date, "%d-%m-%Y"
                        )
                    },
                    {
                        "total_perceptions": sum(
                            slip.line_ids.filtered(
                                lambda line: line.category_id in percep
                            ).mapped("amount")
                        )
                    },
                    {
                        "isr": abs(
                            sum(
                                slip.line_ids.filtered(
                                    lambda line: line.salary_rule_id.l10n_mx_edi_code
                                    == "002"
                                ).mapped("amount")
                            )
                        )
                    },
                    {"alimony": abs(line.amount)},
                    {"beneficiary": alimony[count].partner_id.name},
                    {"payment_way": alimony[count].payment_method_id.name},
                ]
                total_perceptions += line_columns[3]["name"]
                total_isr += line_columns[4]["name"]
                total_alimony += line_columns[5]["name"]
                count += 1
                lines.append(
                    {
                        "id": "02-%s" % employee.id,
                        "parent_id": employee.id,
                        "type": "line",
                        "name": "",
                        "footnotes": {},
                        "columns": line_columns,
                        "level": 2,
                        "unfoldable": False,
                        "unfolded": True,
                        "colspan": 1,
                    }
                )
        total_columns = [
            {"name": ""},
            {"name": ""},
            {"name": None},
            {"name": round(total_perceptions, 2)},
            {"name": round(total_isr, 2)},
            {"name": round(total_alimony, 2)},
            {"name": ""},
            {"name": ""},
        ]
        lines.append(
            {
                "id": "totals",
                "type": "line",
                "name": self.env._("Total"),
                "level": 0,
                "class": "hierarchy_total",
                "columns": total_columns,
                "footnotes": {},
            }
        )
        return lines
