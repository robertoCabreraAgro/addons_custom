from odoo import api, fields, models
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class HrIdseWageReportHandler(models.AbstractModel):
    _name = "hr.idse.wage.report.handler"
    _description = "IDSE report for Wage Update"
    _inherit = "account.report.custom.handler"

    def _custom_options_initializer(self, report, options, previous_options=None):
        res = super()._custom_options_initializer(report, options, previous_options=previous_options)
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
        lines = [
            {
                "counter": None,
                "employer_register": None,
                "nss": None,
                "sbc": None,
                "worker_type": None,
                "wage_type": None,
                "working_type": None,
                "date": None,
                "family_medicine_unit": None,
                "guide": None,
                "employee_code": None,
                "curp": None,
            }
        ]
        contracts = self.env["hr.contract"].search(
            [
                ("state", "=", "open"),
            ]
        )
        date_from = fields.datetime.strptime(options["date"]["date_from"], DEFAULT_SERVER_DATE_FORMAT)
        date_to = fields.datetime.strptime(options["date"]["date_to"], DEFAULT_SERVER_DATE_FORMAT)
        for contract in contracts:
            messages = contract.message_ids.filtered(
                lambda m: m.date.date() >= date_from.date()
                and m.date.date() <= date_to.date()
                and m.message_type == "notification"
            )
            if not messages:
                continue
            tracking = (
                messages.sudo().mapped("tracking_value_ids").filtered(lambda t: t.field_id.name == "l10n_mx_edi_sbc")
            )
            if not tracking:
                continue
            employee = contract.employee_id
            lines.append(
                {
                    "counter": 1,
                    "employer_register": employee.l10n_mx_edi_employer_registration_id.name
                    or employee.company_id.company_registry,
                    "nss": employee.ssnid,
                    "sbc": contract.l10n_mx_edi_sbc,
                    "worker_type": dict(employee._fields["l10n_mx_edi_type"]._description_selection(self.env)).get(
                        str(employee.l10n_mx_edi_type), ""
                    ),
                    "worker_type_value": employee.l10n_mx_edi_type or "",
                    "wage_type": dict(
                        contract._fields["l10n_mx_edi_salary_type"]._description_selection(self.env)
                    ).get(str(contract.l10n_mx_edi_salary_type), ""),
                    "wage_type_value": contract.l10n_mx_edi_salary_type or "",
                    "working_type": dict(
                        contract._fields["l10n_mx_edi_working_type"]._description_selection(self.env)
                    ).get(str(contract.l10n_mx_edi_working_type), ""),
                    "working_type_value": contract.l10n_mx_edi_working_type or "",
                    "date": fields.datetime.strftime(
                        tracking.sorted("create_date")[-1].create_date.date(), "%d-%m-%Y"
                    ),
                    "family_medicine_unit": employee.l10n_mx_edi_medical_unit,
                    "guide": employee.l10n_mx_edi_employer_registration_id.guide,
                    "employee_code": employee.barcode or employee.id,
                    "curp": employee.l10n_mx_curp,
                    "lastname": employee.lastname,
                    "lastname2": employee.lastname2,
                    "firstname": employee.firstname,
                }
            )
        return lines

    def action_get_imss_txt(self, options):
        return self.with_context(**{"no_format": True, "print_mode": True, "raise": True})._l10n_mx_txt_export(options)

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
            data[5] = (str(line["sbc"] or "")).replace(".", "").zfill(6)
            data[6] = "".ljust(6)
            data[7] = line["worker_type_value"] or " "
            data[8] = line["wage_type_value"] or " "
            data[9] = line["working_type_value"] or " "
            data[10] = (line["date"] or "").replace("-", "").ljust(8)
            data[12] = "".ljust(5)
            data[13] = "07"
            data[14] = (line["family_medicine_unit"] or "").ljust(5)
            data[15] = (str(line["guide"]) or "").ljust(10)
            data[16] = " "
            data[17] = (line["employee_code"] or "").ljust(18)
            data[18] = "9"
            lines += "".join(data) + "\n"

        return {
            "file_name": self.env["hr.idse.report.handler"]._get_report_name(),
            "file_content": lines.encode(),
            "file_type": "txt",
        }
