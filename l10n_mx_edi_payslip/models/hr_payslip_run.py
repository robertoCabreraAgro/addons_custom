import csv
import time
from datetime import timedelta
from io import StringIO

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    l10n_mx_edi_payment_date = fields.Date(
        "Payment Date",
        required=True,
        copy=False,
        default=time.strftime("%Y-%m-01"),
        help="Save the payment date that will be added on all payslip created with this batch.",
    )
    l10n_mx_edi_productivity_bonus = fields.Float(
        "Productivity Bonus",
        help="The amount to distribute to the employees in the payslips.",
    )
    l10n_mx_edi_date_start = fields.Date(
        "CFDI Date From",
        help="If the payroll period is different to the dates that must be show in the CFDI, please set here the date "
        "from for the CFDI. If is empty, will be used the Date From.",
    )
    l10n_mx_edi_date_end = fields.Date(
        "CFDI Date To",
        help="If the payroll period is different to the dates that must be show in the CFDI, please set here the date "
        "to for the CFDI. If is empty, will be used the Date To.",
    )
    l10n_mx_edi_payment_date_warning = fields.Char(
        "Payment Date Warning",
        compute="_compute_l10n_mx_edi_payment_date_warning",
        store=True,
    )

    @api.depends("l10n_mx_edi_payment_date", "date_start", "date_end")
    def _compute_l10n_mx_edi_payment_date_warning(self):
        for payslip_run in self.filtered(lambda p: p.l10n_mx_edi_payment_date):
            if not payslip_run.date_start <= payslip_run.l10n_mx_edi_payment_date <= payslip_run.date_end:
                payslip_run.l10n_mx_edi_payment_date_warning = _(
                    "Please note that the payment date falls outside the payslip period. "
                    "Proceed only if this is expected."
                )
            else:
                payslip_run.l10n_mx_edi_payment_date_warning = False

    def action_payslips_done(self):
        self.ensure_one()
        if not self.env.user.has_group("l10n_mx_edi_payslip.allow_validate_payslip"):
            raise UserError(_("Only Managers who are allow to Validate payslip can perform this operation"))
        # using search instead of filtered to keep performance in batch with many payslips
        payslips = self.slip_ids.search([("id", "in", self.slip_ids.ids), ("state", "=", "draft")])
        for payslip in payslips:
            try:
                with self.env.cr.savepoint():
                    payslip.action_payslip_done()
            except UserError as e:
                payslip.l10n_mx_edi_log_error(str(e))
        retry_payslips = (self.slip_ids - payslips).filtered(
            lambda r: r.l10n_mx_edi_pac_status in ["retry", "to_sign", "to_cancel"]
        )
        retry_payslips.l10n_mx_edi_update_pac_status()

    def action_payroll_sent(self):
        """Send email for all signed payslips"""
        self.ensure_one()
        template = self.env.ref("hr_payroll.mail_template_new_payslip", False)
        mail_composition = self.env["mail.compose.message"]
        for payslip in self.slip_ids.filtered(
            lambda p: (
                p.state == "done"
                and not p.sent
                and p.l10n_mx_edi_pac_status == "signed"
                and (p.employee_id.private_email or p.employee_id.work_email)
            )
        ):
            res = mail_composition.create(
                {
                    "model": "hr.payslip",
                    "res_ids": payslip.ids,
                    "template_id": template and template.id or False,
                    "composition_mode": "comment",
                }
            )
            # Send one by one
            # This change is temporary, it is better to send the mails for the employees in the batch at the same time.
            res.action_send_mail()

    def action_set_overtimes(self):
        self.ensure_one()
        self.slip_ids.filtered(lambda s: s.contract_id.l10n_mx_edi_allow_overtimes).auto_generate_overtimes()
        weeks = []
        for day in range((self.date_end - self.date_start).days + 1):
            weeks.append((self.date_start + timedelta(days=day)).isocalendar()[1])
        return {
            "name": _("Overtimes"),
            "view_mode": "list,form",
            "res_model": "hr.payslip.overtime",
            "view_id": False,
            "type": "ir.actions.act_window",
            "domain": [
                ("employee_id", "in", self.slip_ids.mapped("employee_id").ids),
                ("week", "in", weeks),
            ],
            "context": {"search_default_group_by_employee": 1},
        }

    @api.model
    def _get_payslips_dispersion_report_name(self, bank_name=False):
        self.ensure_one()
        name = self.name.replace(" ", "_")
        bank_name = bank_name.replace(" ", "_") if bank_name else _("Dispersions")
        date = self.l10n_mx_edi_payment_date.strftime("%d_%m_%Y")
        return "%s_%s_%s" % (bank_name, date, name)

    @api.model
    def _generate_santander_dispersion(self, slips):
        """For now Dummny method, shows how other banks methods will be structured, replace this docstring
        when santander is supported, this methods must return the lines prepared by the methos
        _prepare_join_dispersion_lines()"""
        return self._generate_bbva_dispersion(slips)

    @api.model
    def _generate_bbva_dispersion(self, payslips):
        """According to BBVA documentation, Gotten from BBVA portal."""
        data = []
        for index, payslip in enumerate(payslips):
            consecutive = str(index + 1).zfill(9).ljust(25)
            bank_account = payslip.employee_id.bank_account_id.acc_number
            bank_account = str(bank_account).ljust(20)
            amount = round(payslip.net_wage, 2)
            amount = f"{amount:.2f}".replace(".", "").zfill(15)
            employee_name = payslip.employee_id.name.ljust(40)[:40].upper()
            name_from, name_to = "ÁÉÍÓÚÑ", "AEIOUN"
            trans = str.maketrans(name_from, name_to)
            employee_name = employee_name.translate(trans)
            # 001 are fixed values, represent bank and branch. 99 Account type
            line = "%s%s%s%s%s%s%s" % (consecutive, "99", bank_account, amount, employee_name, "001", "001")
            data.append({"line": line})
        txt_result = ""
        if data:
            csv.register_dialect("pipe_separator", delimiter="|", skipinitialspace=True)
            output = StringIO()
            writer = csv.DictWriter(output, dialect="pipe_separator", fieldnames=data[0].keys())
            writer.writerows(data)
            txt_result = output.getvalue()
        return txt_result
