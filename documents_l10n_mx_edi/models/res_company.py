import base64
import io
import os
import time
import uuid as uid
import zipfile
from datetime import datetime
import logging
from odoo import api, fields, models
from odoo.exceptions import UserError

ERROR_TYPE = [
    (0, "Token invalido."),
    (1, "Aceptada"),
    (2, "En proceso"),
    (3, "Terminada"),
    (4, "Error"),
    (5, "Rechazada"),
    (6, "Vencida"),
]


_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_mx_edi_esignature_ids = fields.Many2many(
        "l10n_mx_edi.esignature", string="MX E-signature"
    )
    last_sat_fetch_date = fields.Datetime(
        "Last CFDI fetch date", default=fields.Datetime.now
    )

    documents_l10n_mx_edi_folder_settings = fields.Boolean()
    l10n_mx_edi_folder = fields.Many2one(
        "documents.document",
        default=lambda self: self.env.ref(
            "documents_l10n_mx_edi.documents_l10n_mx_edi_folder",
            raise_if_not_found=False,
        ),
    )

    @api.model
    def auto_sync_with_sat(self):
        for company in self.search([("l10n_mx_edi_esignature_ids", "!=", False)]):
            esignature = company.l10n_mx_edi_esignature_ids.get_valid_esignature()
            if not esignature:
                continue

            company.sudo().download_cfdi_files(esignature, {})
            company.last_sat_fetch_date = fields.Datetime.now()
        return True

    @api.model
    def _validate_date_range(self, date_from, date_to):
        return (
            date_from.year == date_to.year
            or date_from.month == date_to.month
            or date_to.day > date_from.day
        )

    def download_cfdi_files(self, esignature, **kwargs):
        ir_attachment = self.env["ir.attachment"]
        docs_document = self.env["documents.document"]
        mx_edi_document = self.env["l10n_mx_edi.document"]
        document_ids = []
        esignature = (
            esignature or self.l10n_mx_edi_esignature_ids.get_valid_esignature()
        )
        date_from = (
            kwargs["date_from"]
            or self.last_sat_fetch_date
            or fields.Datetime.now().replace(month=1, day=1, hour=0, minute=0, second=0)
        )
        date_to = kwargs["date_to"] or fields.Datetime.now().replace(
            hour=0, minute=0, second=0
        )
        certificate = esignature.get_cert_data()[1]
        private_key = esignature.get_pk_data()[1]

        if not self._validate_date_range(date_from, date_to):
            raise UserError(
                """
                Los parámetros de búsqueda no cumple con los requerimientos minimos del SAT\n

                Es importante tener en cuenta las siguientes consideraciones:\n
                    • El SAT sólo emite el CFDI a mes vencido, en caso de que no aparezca deberá\n
                    seguir realizando consultas regulares hasta que se visualice, toda vez que puede\n
                    haber retraso en su emisión.\n
                    • Es importante señalar que de no contar con el RFC, el SAT no podrá emitir los\n
                    CFDI correspondientes, como se informa en el portal de e5cinco en Avisos que\n
                    a la letra dice:\n
                        “En el comprobante de pago SE DEBE INCLUIR CORRECTAMENTE la Razón
                        Social, el Ejercicio del pago y principalmente el RFC, de lo contrario el Servicio de
                        Administración Tributaria (SAT) no emitirá el Certificado Fiscal Digital por Internet
                        (CFDI)”.\n
                    • Finalmente, deberá asegurar que los datos que se proporcionen coincidan con\n
                    los que contienen los documentos, a fin de que la verificación sea exitosa.\n
            """
            )

        token_res = mx_edi_document.l10n_mx_ws_generate_token(certificate, private_key)
        ses = self.env["l10n_mx_edi.session"].create(
            {
                "company_id": self.id,
                "token": token_res["token"],
                "token_expiration": datetime.fromisoformat(token_res["expires"]),
                "date_from": date_from,
                "date_to": date_to,
            }
        )
        request_res = mx_edi_document.l10n_mx_ws_request_download(
            certificate,
            private_key,
            ses.token,
            {"date_from": date_from, "date_to": date_to},
        )
        ses.write(
            {
                "request": request_res["id_solicitud"],
                "request_status_code": request_res["cod_estatus"],
                "request_message": request_res["mensaje"],
            }
        )
        content = []
        for _ in range(5):
            if ses.token_expiration < fields.Datetime.now():
                token_res = mx_edi_document.l10n_mx_ws_generate_token(
                    certificate, private_key
                )
                ses.write(
                    {
                        "token": token_res["token"],
                        "token_expiration": datetime.fromisoformat(
                            token_res["expires"]
                        ),
                    }
                )
            verify_download = mx_edi_document.l10n_mx_ws_verify_package(
                certificate, private_key, ses.token, ses.request
            )
            ses.write(
                {
                    "request_state": verify_download["estado_solicitud"],
                    "file_count": int(verify_download["numero_cfdis"]),
                    "request_message": verify_download["mensaje"],
                }
            )

            if int(ses.request_state) <= 2:
                time.sleep(20)
                continue

            if int(ses.request_state) >= 3:  # Error=4
                if int(ses.request_state) >= 4:
                    message = f"{ERROR_TYPE[ses.request_state]} - {ses.request_message}"
                    self.env["bus.bus"]._sendone(
                        self.env.user.partner_id,
                        "simple_notification",
                        {
                            "title": "Error",
                            "message": message,
                            "sticky": False,
                            "warning": True,
                        },
                    )
                break

        if int(ses.request_state) != 3:  # Terminada=3
            return []

        download_res = mx_edi_document.l10n_mx_ws_download_package(
            certificate, private_key, ses.token, verify_download["paquetes"][0]
        )
        if download_res["paquete_b64"]:
            content = download_res["paquete_b64"]
            folder_id = self.l10n_mx_edi_folder.id or False  # Precompute folder ID once

            # Batch processing preparation
            att_vals_list = []  # Stores attachment creation values
            doc_vals_list = []  # Stores document creation values

            with zipfile.ZipFile(io.BytesIO(base64.b64decode(content))) as container:

                # Filtering only XML files and extract clean names (without extension)
                xml_files = [
                    (fname, os.path.splitext(fname)[0].upper())
                    for fname in container.namelist()
                    if fname.lower().endswith(".xml")
                ]

                if xml_files:
                    # Extract just the names for existence check
                    names = [xml_file[1] for xml_file in xml_files]

                    # Find all existing documents
                    existing_docs = docs_document.sudo().search(
                        [("name", "in", names), ("company_id", "=", self.id)]
                    )

                    # Existing documents are kept for return
                    document_ids.extend(existing_docs.ids)

                    # already processed files
                    existing_names = set(existing_docs.mapped("name"))

                    for fname, name in xml_files:

                        if name in existing_names:
                            continue  # Skip already processed files

                        with container.open(fname) as file:
                            file_content = base64.b64encode(file.read())

                            if not mx_edi_document._l10n_mx_edi_is_cfdi(file_content):
                                continue  # Skip non-CFDI XMLs

                            # Prepare for batch creation
                            att_vals_list.append(
                                {
                                    "name": f"{name}.xml",
                                    "type": "binary",
                                    "datas": file_content,
                                }
                            )
                            doc_vals_list.append(
                                {
                                    "name": name,
                                    "folder_id": folder_id,
                                    "l10n_mx_edi_is_cfdi": True,
                                }
                            )

            # Bulk create records if we have valid files
            if att_vals_list:

                # Create all attachments in single operation
                attachments = ir_attachment.with_context(
                    force_l10n_mx_edi_cfdi_uuid=True
                ).create(att_vals_list)

                # Assign attachment IDs to corresponding documents
                for attachment, doc_vals in zip(attachments, doc_vals_list):
                    doc_vals["attachment_id"] = attachment.id

                # Bulk create all documents
                created_documents = docs_document.create(doc_vals_list)
                document_ids.extend(created_documents.ids)

        action = self.env.ref("documents.document_action").read()[0]
        action["domain"] = [("id", "in", document_ids)]
        return action
