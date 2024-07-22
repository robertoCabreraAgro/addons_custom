from odoo import _, api, models
from odoo.exceptions import UserError


def create_list_html(array):
    """Convert an array of string to a html list.
    :param list array: A list of strings
    :return: empty string if not array, an html list otherwise.
    :rtype: str"""
    if not array:
        return ""
    msg = ""
    for item in array:
        msg += "<li>" + item + "</li>"
    return "<ul>" + msg + "</ul>"


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    def action_print_payroll_dispersion(self):
        """Gets the dispersion files to all the banks in the employee payslips"""
        self.ensure_one()
        self._check_can_generate_dispersion()
        ids = {"list_ids": ",".join(str(x) for x in self.ids)}
        return {
            "name": "PayslipDispersion",
            "type": "ir.actions.act_url",
            "url": "/print/payslip/dispersions?list_ids=%(list_ids)s" % ids,
        }

    def _check_can_generate_dispersion(self):
        self.ensure_one()
        if not self.env.user.has_group("hr_bank_dispersion.allow_print_payslip_dispersion"):
            raise UserError(
                _(
                    "Only Managers with the group 'Allow to Print Payslip Dispersion' can generate "
                    "payslip dispersion files"
                )
            )

        bank_ids = self.mapped("slip_ids.employee_id.bank_account_id.bank_id")
        if not bank_ids:
            raise UserError(
                _(
                    "To use this option, please configure the bank account on your employees, "
                    "no employees are currently configured."
                )
            )

        # Check if there is any bank with a method to generate dispersion
        bank_errors = []
        dispersion_methods = []
        for bank in bank_ids:
            dispersion_method = "_generate_%s_dispersion" % bank.name.split(" ")[0].lower()
            if not hasattr(self, dispersion_method):
                bank_errors.append(bank.name)
                continue
            dispersion_methods.append(dispersion_method)

        if not any(dispersion_methods):
            raise UserError(
                _(
                    "We currently do not support generating payroll dispersions for "
                    "any of the employee banks in this payroll batch."
                )
            )

        if bank_errors:
            body_msg = _("The following of your banks are not available for payroll dispersion")
            self.message_post(body=body_msg + create_list_html(bank_errors))

    def _get_payslips_dispersions(self):
        """Get the payslip dispersions, 1 for each bank on payslip batch
        :return: List of tuples, 2 values. Report name and text
        :rtype: list"""
        dispersions = []

        for bank_id in self.mapped("slip_ids.employee_id.bank_account_id.bank_id"):
            # using search instead filtered to keep performance in batch with many payslips like action_payslips_done()
            payslips = self.slip_ids.search(
                [("id", "in", self.slip_ids.ids), ("employee_id.bank_account_id.bank_id", "=", bank_id.id)]
            )
            # Call generate dispersion methods with the first word of the bank name
            # The method must return lines prepared by _prepare_join_dispersion_lines
            bank_func = "_generate_%s_dispersion" % bank_id.name.split(" ")[0].lower()
            try:
                text = getattr(self, bank_func)(payslips)
            except AttributeError:
                continue
            file_name = self._get_payslips_dispersion_report_name(bank_id.name)
            dispersions.append((file_name, text))

        return dispersions

    @api.model
    def _get_payslips_dispersion_report_name(self, bank_name=False):
        self.ensure_one()
        name = self.name.replace(" ", "_")
        bank_name = bank_name.replace(" ", "_") if bank_name else _("Dispersions")
        date = self.date_end.strftime("%d_%m_%Y")
        return "%s_%s_%s" % (bank_name, date, name)

    @api.model
    def _generate_ing_dispersion(self, payslips):
        """Base method to example."""
        lines = []
        for index, payslip in enumerate(payslips):
            consecutive = str(index + 1).zfill(9).ljust(25)
            bank_account = payslip.employee_id.bank_account_id.acc_number
            bank_account = str(bank_account).ljust(20)
            amount = payslip.net_wage
            amount = str(amount).replace(".", "").zfill(15)
            employee_name = payslip.employee_id.name.ljust(40)[:40]
            # 001 are fixed values, represent bank and branch. 99 Account type
            line = "%s%s%s%s%s%s%s" % (consecutive, "99", bank_account, amount, employee_name, "001", "001")
            lines.append(line)
        return self._prepare_join_dispersion_lines(lines)

    @api.model
    def _prepare_join_dispersion_lines(self, lines):
        """This method was implemented because the text generation is using the linux end of a line format, and the
        banks (BBVA for example) are expecting the windows format.

        \r = CR (Carriage Return) -> Used as a new line character in Mac OS before X
        \n = LF (Line Feed) → Used as a new line character in Unix/Mac OS X
        \r\n = CR + LF → Used as a new line character in Windows"""
        return "\r\n".join(lines) + "\r\n"
