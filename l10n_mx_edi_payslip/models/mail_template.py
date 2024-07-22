from odoo import models


class MailTemplate(models.Model):
    _inherit = "mail.template"

    def _generate_template_attachments(self, res_ids, render_fields, render_results=None):
        self.ensure_one()
        res = super()._generate_template_attachments(res_ids, render_fields, render_results)
        if self.model != "hr.payslip":
            return res

        for payslip in self.env["hr.payslip"].browse(res_ids):
            company = payslip.company_id or payslip.contract_id.company_id
            if company.country_id != self.env.ref("base.mx"):
                continue  # pragma: no cover
            attachment = payslip.l10n_mx_edi_retrieve_last_attachment()
            if attachment:
                res[payslip.id].get("attachments", []).append((attachment.name, attachment.datas))
        return res
