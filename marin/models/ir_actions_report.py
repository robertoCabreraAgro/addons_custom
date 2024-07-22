from odoo import models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        report_content, report_format = super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
        if self._is_invoice_report(report_ref):
            invoices = self.env["account.move"].browse(res_ids)
            if invoices._is_valid_generate_document_from_report() and report_format == "pdf":
                invoices._generate_document_from_report(report_content)
        return report_content, report_format
