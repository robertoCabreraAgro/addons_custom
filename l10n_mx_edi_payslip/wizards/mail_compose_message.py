from odoo import models

from odoo.addons.mail.tools.parser import parse_res_ids


class MailComposeMessage(models.TransientModel):
    _inherit = "mail.compose.message"

    def send_mail(self, auto_commit=False):
        res = super().send_mail(auto_commit)
        if "hr.payslip" in self.mapped("model"):
            records = self.env["hr.payslip"].browse(parse_res_ids(self.res_ids))
            records.write({"sent": True})
        return res

    def _action_send_mail(self, auto_commit=False):
        res = super()._action_send_mail(auto_commit=auto_commit)
        if "hr.payslip" in self.mapped("model"):
            self.env["hr.payslip"].browse(parse_res_ids(self.res_ids)).write({"sent": True})
        return res
