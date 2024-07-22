import base64
import io
import time
import uuid as uid
import zipfile
from datetime import datetime

from odoo import api, fields, models

ERROR_TYPE = [
    (0, "Token invalido."),
    (1, "Aceptada"),
    (2, "En proceso"),
    (3, "Terminada"),
    (4, "Error"),
    (5, "Rechazada"),
    (6, "Vencida"),
]


# import logging
# _logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_mx_edi_esignature_ids = fields.Many2many("l10n_mx_edi.esignature", string="MX E-signature")
    last_sat_fetch_date = fields.Datetime("Last CFDI fetch date", default=fields.Datetime.now)

    documents_l10n_mx_edi_folder_settings = fields.Boolean()
    l10n_mx_edi_folder = fields.Many2one(
        "documents.folder",
        default=lambda self: self.env.ref(
            "documents_l10n_mx_edi.documents_l10n_mx_edi_folder", raise_if_not_found=False
        ),
    )

    @api.model
    def auto_sync_with_sat(self):
        for company in self.search([("l10n_mx_edi_esignature_ids", "!=", False)]):
            esignature = company.l10n_mx_edi_esignature_ids.get_valid_esignature()
            if not esignature:
                continue
            company.sudo().download_cfdi_files(esignature=esignature)
            company.last_sat_fetch_date = fields.Datetime.now()
        return True

    def download_cfdi_files(self, esignature):
        edi_obj = self.env["l10n_mx_edi.document"]
        sanitized = {}
        sanitized["date_from"] = self.last_sat_fetch_date or fields.Datetime.now().replace(
            month=1, day=1, hour=0, minute=0, second=0
        )
        sanitized["date_to"] = fields.Datetime.now().replace(hour=0, minute=0, second=0)
        _cer_pem, certificate = esignature.get_cert_data()
        _key_pem, private_key = esignature.get_pk_data()
        uuid = uid.uuid4()
        token_res = edi_obj.l10n_mx_ws_generate_token(certificate, private_key, uuid)
        ses = self.env["l10n_mx_edi.session"].create(
            {
                "company_id": self.id,
                "uuid": uuid,
                "token": token_res["token"],
                "token_expiration": datetime.fromisoformat(token_res["expires"]),
                "date_from": sanitized["date_from"],
                "date_to": sanitized["date_to"],
            }
        )
        sanitized["uuid"] = uuid
        request_res = edi_obj.l10n_mx_ws_request_download(certificate, private_key, ses.token, sanitized)
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
                uuid = uid.uuid4()  # TODO do I need to recompute this?
                token_res = edi_obj.l10n_mx_ws_generate_token(certificate, private_key, uuid)
                ses.write(
                    {
                        "uuid": uuid,
                        "token": token_res["token"],
                        "token_expiration": datetime.fromisoformat(token_res["expires"]),
                    }
                )
            verify_download = edi_obj.l10n_mx_ws_verify_package(certificate, private_key, ses.token, ses.request)
            ses.write(
                {
                    "request_state": int(verify_download["estado_solicitud"]),
                    "file_count": int(verify_download["numero_cfdis"]),
                    "request_message": verify_download["mensaje"],
                }
            )
            if ses.request_state <= 2:
                time.sleep(20)
                continue
            if ses.request_state >= 4:
                message = f"{ERROR_TYPE[ses.request_state]} - {ses.request_message}"
                self.env["bus.bus"]._sendone(
                    self.env.user.partner_id,
                    "simple_notification",
                    {"title": "Error", "message": message, "sticky": False, "warning": True},
                )
                break
            download_res = edi_obj.l10n_mx_ws_download_package(
                certificate, private_key, ses.token, verify_download["paquetes"]
            )
            if download_res["paquete_b64"]:
                content.append(download_res["paquete_b64"])
        if not content:
            return []

        att_obj = self.env["ir.attachment"]
        doc_obj = self.env["documents.document"]
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(content[0]))) as container:
            for fname in container.namelist():
                name = fname.split(".")[0].upper()
                doc_exist = doc_obj.sudo().search([("name", "=", name), ("company_id", "=", self.id)])
                if doc_exist:
                    continue
                with container.open(fname) as file:
                    file_content = base64.b64encode(file.read())
                    is_cfdi, _is_cfdi_signed, _cfdi_etree = self.env["l10n_mx_edi.document"].check_objectify_xml(
                        file_content
                    )
                    if is_cfdi:
                        att_exist = att_obj.with_context(force_l10n_mx_edi_cfdi_uuid=True).create(
                            {
                                "name": name + ".xml",
                                "type": "binary",
                                "datas": file_content,
                                "l10n_mx_edi_cfdi_uuid": name,
                            }
                        )
                        doc_obj.create(
                            {
                                "name": name,
                                "attachment_id": att_exist.id,
                                "folder_id": self.l10n_mx_edi_folder.id or False,
                                "l10n_mx_edi_is_cfdi": True,
                            }
                        )
