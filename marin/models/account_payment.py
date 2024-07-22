from werkzeug.urls import url_quote_plus

from odoo import _, fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    cash_transfer_pos_id = fields.Many2one("pos.session")
    client_receipt_document_share_id = fields.Many2one("documents.share", readonly=True)
    payment_receipt_document_share_id = fields.Many2one("documents.share", readonly=True)

    def action_post(self):
        res = super().action_post()
        folder = self.env.ref("marin.documents_payment_receipts_folder")
        if self.partner_type == "customer":
            if not self.client_receipt_document_share_id:
                self.client_receipt_document_share_id = self.env["documents.share"].create(
                    {
                        "type": "ids",
                        "name": "share_link_ids",
                        "folder_id": folder.id,
                    }
                )
            if not self.payment_receipt_document_share_id:
                self.payment_receipt_document_share_id = self.env["documents.share"].create(
                    {
                        "type": "ids",
                        "name": "share_link_ids",
                        "folder_id": folder.id,
                    }
                )
            self._generate_client_receipt_from_report()
            self._generate_payment_receipt_from_report()
        return res

    def _generate_client_receipt_from_report(self):
        doc_name = _("Client Receipt %s", self.name)
        document = self._generate_document_from_report(doc_name, "marin.action_report_payment_receipt")
        self.client_receipt_document_share_id.document_ids.attachment_id.unlink()
        self.client_receipt_document_share_id.document_ids.unlink()
        self.client_receipt_document_share_id.document_ids = [(4, document.id)]

    def _generate_payment_receipt_from_report(self):
        doc_name = _("Payment Receipt %s", self.name)
        document = self._generate_document_from_report(doc_name, "account.action_report_payment_receipt")
        self.payment_receipt_document_share_id.document_ids.attachment_id.unlink()
        self.payment_receipt_document_share_id.document_ids.unlink()
        self.payment_receipt_document_share_id.document_ids = [(4, document.id)]

    def _generate_document_from_report(self, doc_name, report_xml_id):
        report_content, _report_format = self.env["ir.actions.report"]._render_qweb_pdf(report_xml_id, self.id)
        folder = self.env.ref("marin.documents_payment_receipts_folder")
        attachment = self.env["ir.attachment"].create(
            {
                "name": doc_name,
                "raw": report_content,
                "mimetype": "application/pdf",
            }
        )
        return self.env["documents.document"].create(
            {
                "folder_id": folder.id,
                "name": doc_name,
                "attachment_id": attachment.id,
            }
        )

    def _get_client_receipt_qr(self):
        barcode_value = url_quote_plus(self.client_receipt_document_share_id.full_url)
        barcode_src = f"/report/barcode/?barcode_type=QR&value={barcode_value}&width=120&height=120"
        return barcode_src

    def _get_payment_receipt_qr(self):
        barcode_value = url_quote_plus(self.payment_receipt_document_share_id.full_url)
        barcode_src = f"/report/barcode/?barcode_type=QR&value={barcode_value}&width=120&height=120"
        return barcode_src
