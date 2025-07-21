from odoo import http

from odoo.addons.documents.controllers.documents import ShareRoute


class DocumentsShareRoute(ShareRoute):
    def _documents_upload_create_write(self, document_sudo, vals):
        # Check for duplicates before attempting creation
        name = vals.get("name", "")
        if not name and vals.get("attachment_id"):
            name = http.request.env["ir.attachment"].browse(vals["attachment_id"]).name
        if name and name.lower().endswith(".xml"):
            mx_edi_document = http.request.env["l10n_mx_edi.document"]
            duplicate_result = mx_edi_document._get_duplicate_cfdi(
                name, http.request.env["documents.document"]
            )
            if duplicate_result["duplicated"]:
                # Send notification for duplicate
                http.request.env["bus.bus"]._sendone(
                    http.request.env.user.partner_id,
                    "simple_notification",
                    {
                        "title": "Duplicated CFDI",
                        "message": duplicate_result["message"],
                        "sticky": False,
                        "warning": True,
                    },
                )
                # Return the existing document and skip the message_post
                existing_doc = duplicate_result["document"]
                if existing_doc:
                    existing_doc.message_post(
                        body="Document uploaded (duplicate detected)"
                    )
                    return existing_doc

                # No existing document found, skip creation
                return None

        # Continue with normal flow for non-duplicates
        return super()._documents_upload_create_write(document_sudo, vals)
