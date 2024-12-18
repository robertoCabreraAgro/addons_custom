# pylint: disable=missing-return
from odoo import api, fields, models
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class HrSuaReportHandler(models.AbstractModel):
    _name = "hr.sua.report.handler"
    _description = "SUA report"
    _inherit = "account.report.custom.handler"

    def _custom_options_initializer(self, report, options, previous_options=None):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options["columns"] = list(options["columns"])
        options.setdefault("buttons", []).extend(
            (
                {
                    "name": self.env._("Export IMSS (TXT)"),
                    "sequence": 40,
                    "action": "export_file",
                    "action_param": "action_get_imss_txt",
                    "file_export_type": self.env._("IMSS TXT"),
                },
            )
        )

    def _report_custom_engine_sua_report(
        self, expressions, options, date_scope, current_groupby, next_groupby, offset=0, limit=None, warnings=None
    ):
        def build_dict(report, current_groupby, query_res):
            if not current_groupby:
                return query_res[0] if query_res else {k: None for k in report.mapped("line_ids.expression_ids.label")}
            return [(group_res["grouping_key"], group_res) for group_res in query_res]

        report = self.env["account.report"].browse(options["report_id"])
        query_res = self._get_lines(options)
        return build_dict(report, current_groupby, query_res)

    @api.model
    def _get_lines(self, options, line_id=None):
        lines = []
        contracts = self.env["hr.contract"].search(
            [
                ("state", "=", "open"),
            ]
        )
        date_from = fields.datetime.strptime(options["date"]["date_from"], DEFAULT_SERVER_DATE_FORMAT).date()
        date_to = fields.datetime.strptime(options["date"]["date_to"], DEFAULT_SERVER_DATE_FORMAT).date()
        for contract in contracts:
            employee = contract.employee_id
            loan = employee.loan_ids.filtered(
                lambda loan: loan.infonavit_type
                and (loan.payment_term == -1 or loan.payslips_count < loan.payment_term)
                and (not loan.date_from or loan.date_from >= date_from)
                and (not loan.date_to or loan.date_to <= date_to)
            )
            if not loan or not (contract.date_start >= date_from and contract.date_start <= date_to):
                continue
            lines.append(
                {
                    "counter": 1,
                    "employer_register": employee.l10n_mx_edi_employer_registration_id.name
                    or employee.company_id.company_registry,
                    "nss": employee.ssnid,
                    "vat": employee.l10n_mx_rfc,
                    "curp": employee.l10n_mx_curp,
                    "worker_type": dict(employee._fields["l10n_mx_edi_type"]._description_selection(self.env)).get(
                        str(employee.l10n_mx_edi_type), ""
                    ),
                    "worker_type_value": employee.l10n_mx_edi_type or "",
                    "working_type": dict(
                        contract._fields["l10n_mx_edi_working_type"]._description_selection(self.env)
                    ).get(str(contract.l10n_mx_edi_working_type), ""),
                    "working_type_value": contract.l10n_mx_edi_working_type or "",
                    "date": fields.datetime.strftime(contract.date_start, "%d-%m-%Y"),
                    "sdi": contract.l10n_mx_edi_sdi_total,
                    "employee_key": employee.pin,
                    "infonavit_number": loan.name,
                    "date_start": fields.datetime.strftime(loan.date_from, "%d-%m-%Y") if loan else False,
                    "discount_type": dict(loan._fields["infonavit_type"]._description_selection(self.env)).get(
                        str(loan.infonavit_type), ""
                    ),
                    "discount_type_value": loan.infonavit_type.replace("percentage", "1")
                    .replace("fixed_amount", "2")
                    .replace("vsm", "3"),
                    "discount_amount": loan.amount,
                    "lastname": employee.lastname,
                    "lastname2": employee.lastname2,
                    "firstname": employee.firstname,
                }
            )
        return lines

    def action_get_imss_txt(self, options):
        return self.with_context(**{"no_format": True, "print_mode": True, "raise": True})._l10n_mx_txt_export(options)

    def _l10n_mx_txt_export(self, options):
        lines = ""
        txt_data = self._get_lines(options)
        for line in txt_data:
            if not line.get("counter"):
                continue
            data = [""] * 14
            data[0] = (line["employer_register"] or "").ljust(11).upper()
            data[1] = (line["nss"] or "").ljust(11)[:11]
            data[2] = (line["vat"] or "").ljust(13).upper()
            data[3] = (line["curp"] or "").ljust(18).upper()
            data[4] = (
                (
                    "%s$%s$%s"
                    % (
                        line["lastname"] or line["lastname2"] or "",
                        line["lastname2"] or "" if line["lastname"] else "",
                        line["firstname"] or "",
                    )
                )
                .ljust(50)[:50]
                .upper()
            )
            data[5] = line["worker_type_value"] or " "
            data[6] = line["working_type_value"] or " "
            data[7] = (line["date"] or "").replace("-", "").ljust(8)
            data[8] = (str(line["sdi"] or "")).replace(".", "").zfill(7)
            data[9] = (line["employee_key"] or " ").ljust(17).upper()
            data[10] = (line["infonavit_number"] or "").ljust(10)[:10]
            data[11] = (line["date_start"] or "").replace("-", "").zfill(8)
            data[12] = line["discount_type_value"] or "0"
            data[13] = (str(line["discount_amount"] or "")).replace(".", "").zfill(8)
            lines += "".join(data).upper() + "\n"
        return {
            "file_name": self._get_report_name(),
            "file_content": lines.encode(),
            "file_type": "txt",
        }

    def _get_report_name(self):
        # Get the month and year from report date filters if exists
        date = fields.date.today()
        if self._context.get("report_date"):
            date = fields.datetime.strptime(self._context["report_date"], "%Y-%m-%d")
        company = self.env.company
        vat = company.vat or ""
        return "SUA_%s_%s" % (vat, date.strftime("%Y%m"))
