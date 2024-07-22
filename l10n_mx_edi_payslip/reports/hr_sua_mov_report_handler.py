# pylint: disable=missing-return
from datetime import datetime

from odoo import _, api, fields, models
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class HrSuaMovReportHandler(models.AbstractModel):
    _name = "hr.sua.mov.report.handler"
    _description = "SUA report Movements"
    _inherit = "account.report.custom.handler"

    filter_date = {"mode": "range", "filter": "this_month"}
    filter_hierarchy = None

    def _custom_options_initializer(self, report, options, previous_options=None):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options["columns"] = list(options["columns"])
        options.setdefault("buttons", []).extend(
            (
                {
                    "name": _("Export IMSS (TXT)"),
                    "sequence": 40,
                    "action": "export_file",
                    "action_param": "action_get_imss_txt",
                    "file_export_type": _("IMSS TXT"),
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
        lines = [
            {
                "counter": None,
                "employer_register": None,
                "nss": None,
                "movement_type": None,
                "date": None,
                "inability_number": None,
                "days": None,
                "sdi": None,
            }
        ]
        employees = self.env["hr.employee"].search([("active", "in", [False, True])])
        date_from = fields.datetime.strptime(options["date"]["date_from"], DEFAULT_SERVER_DATE_FORMAT).date()
        date_to = fields.datetime.strptime(options["date"]["date_to"], DEFAULT_SERVER_DATE_FORMAT).date()
        for employee in employees:
            if not employee.active and employee.departure_date >= date_from and employee.departure_date <= date_to:
                lines.append(
                    {
                        "counter": 1,
                        "employer_register": employee.l10n_mx_edi_employer_registration_id.name
                        or employee.company_id.company_registry,
                        "nss": employee.ssnid,
                        "movement_type": "Baja",
                        "movement_type_value": "02",
                        "date": fields.datetime.strftime(employee.departure_date, "%d-%m-%Y"),
                        "inability_number": employee.l10n_mx_edi_employer_registration_id.guide,
                        "days": employee.barcode or employee.id,
                        "sdi": employee.contract_id.l10n_mx_edi_sdi_total,
                    }
                )
                continue
            contract = employee.contract_id
            if not contract:
                continue
            show = False
            messages = contract.message_ids.filtered(
                lambda m: m.date.date() >= date_from and m.date.date() <= date_to and m.message_type == "notification"
            )
            if messages:
                tracking = (
                    messages.sudo()
                    .mapped("tracking_value_ids")
                    .filtered(lambda t: t.field_id.name == "l10n_mx_edi_sbc")
                )
                if tracking:
                    lines.append(
                        {
                            "counter": 1,
                            "employer_register": employee.l10n_mx_edi_employer_registration_id.name
                            or employee.company_id.company_registry,
                            "nss": employee.ssnid,
                            "movement_type": "Wage Update",
                            "movement_type_value": "07",
                            "date": fields.datetime.strftime(
                                tracking.sorted("create_date")[-1].create_date.date(), "%d-%m-%Y"
                            ),
                            "inability_number": "",
                            "days": "",
                            "sdi": employee.contract_id.l10n_mx_edi_sdi_total,
                        }
                    )
                    show = True

            # Ausencias
            leave = self.env.ref("hr_work_entry_contract.work_entry_type_unpaid_leave")
            domain = [("work_entry_type_id", "=", leave.id)]
            leaves = contract._get_worked_leaves(
                datetime.combine(date_from, datetime.min.time()),
                datetime.combine(date_to, datetime.max.time()),
                domain=domain,
            )
            if leaves:
                leaves = self.env["hr.leave"]
                work_entry = self.env["hr.work.entry"].search(
                    contract._get_work_hours_domain(date_from, date_to, domain=domain, inside=True)
                )
                for entry in work_entry:
                    if entry.leave_id in leaves:
                        continue
                    lines.append(
                        {
                            "counter": 1,
                            "employer_register": employee.l10n_mx_edi_employer_registration_id.name
                            or employee.company_id.company_registry,
                            "nss": employee.ssnid,
                            "movement_type": "Leaves",
                            "movement_type_value": "11",
                            "date": fields.datetime.strftime(entry.leave_id.date_from.date(), "%d-%m-%Y"),
                            "inability_number": "",
                            "days": int(entry.leave_id.number_of_days),
                            "sdi": employee.contract_id.l10n_mx_edi_sdi_total,
                        }
                    )
                    leaves |= entry.leave_id
                show = True
            # Incapacidades
            leave = self.env.ref("hr_work_entry_contract.work_entry_type_sick_leave")
            domain = [("work_entry_type_id", "=", leave.id)]
            leaves = contract._get_worked_leaves(
                datetime.combine(date_from, datetime.min.time()),
                datetime.combine(date_to, datetime.max.time()),
                domain=domain,
            )
            if leaves:
                leaves = self.env["hr.leave"]
                work_entry = self.env["hr.work.entry"].search(
                    contract._get_work_hours_domain(date_from, date_to, domain=domain, inside=True)
                )
                for entry in work_entry:
                    if entry.leave_id in leaves:
                        continue
                    lines.append(
                        {
                            "counter": 1,
                            "employer_register": employee.l10n_mx_edi_employer_registration_id.name
                            or employee.company_id.company_registry,
                            "nss": employee.ssnid,
                            "movement_type": "Inability",
                            "movement_type_value": "12",
                            "date": fields.datetime.strftime(entry.leave_id.date_from.date(), "%d-%m-%Y"),
                            "inability_number": entry.leave_id.name,
                            "days": int(entry.leave_id.number_of_days),
                            "sdi": employee.contract_id.l10n_mx_edi_sdi_total,
                        }
                    )
                    leaves |= entry.leave_id
                show = True
            if not show:
                lines.pop()
        return lines

    def action_get_imss_txt(self, options):
        return self.with_context(**{"no_format": True, "print_mode": True, "raise": True})._l10n_mx_txt_export(options)

    def _l10n_mx_txt_export(self, options):
        lines = ""
        txt_data = self._get_lines(options)
        for line in txt_data:
            if not line.get("counter"):
                continue
            data = [""] * 7
            data[0] = (line["employer_register"] or "").ljust(11)
            data[1] = (line["nss"] or "").ljust(11)[:11]
            data[2] = line["movement_type_value"] or "  "
            data[3] = (line["date"] or "").replace("-", "").ljust(8)
            data[4] = (line["inability_number"] or "").ljust(8)[:8]
            data[5] = (str(line["days"]) or "").zfill(2)
            data[6] = (str(line["sdi"] or "")).replace(".", "").zfill(7)
            lines += "".join(data).upper() + "\n"

        return {
            "file_name": self.env["hr.sua.report.handler"]._get_report_name(),
            "file_content": lines.encode(),
            "file_type": "txt",
        }
