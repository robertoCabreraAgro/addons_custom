from odoo import api, fields, models


class HrIdseBajaReportHandler(models.AbstractModel):
    _name = "hr.idse.baja.report.handler"
    _description = "IDSE report Baja"
    _inherit = "account.report.custom.handler"

    def _custom_options_initializer(self, report, options, previous_options=None):
        res = super()._custom_options_initializer(
            report, options, previous_options=previous_options
        )
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
        return res

    def _report_custom_engine_idse_report(
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
        query_res = self._get_lines(options)
        return build_dict(report, current_groupby, query_res)

    @api.model
    def _get_lines(self, options, line_id=None):
        lines = [
            {
                "counter": None,
                "employer_register": None,
                "nss": None,
                "date": None,
                "guide": None,
                "employee_code": None,
                "reason": None,
            }
        ]
        employees = self.env["hr.employee"].search(
            [
                ("active", "=", False),
                ("departure_date", ">=", options["date"]["date_from"]),
                ("departure_date", "<=", options["date"]["date_to"]),
            ]
        )
        for employee in employees:
            lines.append(
                {
                    "counter": 1,
                    "employer_register": employee.l10n_mx_edi_employer_registration_id.name
                    or employee.company_id.company_registry,
                    "nss": employee.ssnid,
                    "date": fields.datetime.strftime(
                        employee.departure_date, "%d-%m-%Y"
                    ),
                    "guide": employee.l10n_mx_edi_employer_registration_id.guide,
                    "employee_code": employee.barcode or employee.id,
                    "reason": employee.departure_reason_id.l10n_mx_code,
                    "lastname": employee.lastname,
                    "lastname2": employee.lastname2,
                    "firstname": employee.firstname,
                }
            )
        return lines

    def action_get_imss_txt(self, options):
        return self.with_context(
            **{"no_format": True, "print_mode": True, "raise": True}
        )._l10n_mx_txt_export(options)

    def _l10n_mx_txt_export(self, options):
        txt_data = self._get_lines(options)
        lines = ""
        for line in txt_data:
            if not line.get("counter"):
                continue
            data = [""] * 20
            data[0] = (line["employer_register"] or "").ljust(11)
            data[1] = (line["nss"] or "").ljust(11)[:11]
            data[2] = (line["lastname"] or "").ljust(27)[:27].upper()
            data[3] = (line["lastname2"] or "").ljust(27)[:27].upper()
            data[4] = (line["firstname"] or "").ljust(27)[:27].upper()
            data[6] = "".zfill(15)
            data[10] = (line["date"] or "").replace("-", "").ljust(8)
            data[12] = "".ljust(5)
            data[13] = "02"
            data[14] = (line["guide"] or "").ljust(5)
            data[15] = (str(line["employee_code"]) or "").ljust(10)
            data[16] = str(line["reason"] or "")
            data[17] = "".ljust(18)
            data[18] = "9"
            lines += "".join(data) + "\n"

        return {
            "file_name": self.env["hr.idse.report.handler"]._get_report_name(),
            "file_content": lines.encode(),
            "file_type": "txt",
        }
