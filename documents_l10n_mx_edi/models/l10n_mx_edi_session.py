import base64
import io
import os
import zipfile
import logging
import pytz
import time

from datetime import datetime, timedelta
from odoo import api, fields, models

from .l10n_mx_edi_document import MXWS_ERROR_TYPE

DEFAULT_TZ = "America/Mexico_City"

_logger = logging.getLogger(__name__)


class Session(models.Model):
    _name = "l10n_mx_edi.session"
    _description = "MX SAT session"
    _order = "create_date desc"

    name = fields.Date(
        "Date", required=True, index=True, default=fields.Date.context_today
    )
    company_id = fields.Many2one(
        "res.company", "Company", default=lambda self: self.env.company
    )
    uuid = fields.Char("UUID")
    token = fields.Char()
    token_expiration = fields.Datetime()
    date_from = fields.Datetime("Date from")
    date_to = fields.Datetime("Date to")
    request = fields.Char("Request ID")
    request_status_code = fields.Char("Request code")
    request_state = fields.Selection(MXWS_ERROR_TYPE, "Request state")
    request_message = fields.Char("Request message")
    file_count = fields.Integer("File count")
    packages = fields.Char("packages")
    document_ids = fields.Many2many(
        "documents.document",
        "document_l10n_mx_edi_session_rel",
        "l10n_mx_edi_session_id",
        "document_id",
        string="Documents",
    )
    count_verify = fields.Integer()

    def get_mx_current_datetime(self):
        return fields.Datetime.context_timestamp(
            self.with_context(tz="America/Mexico_City"), fields.Datetime.now()
        )

    def action_verify_cfdi(self, esignature=None, max_retries=2, waiting_sec=0):
        self.ensure_one()

        mx_edi_document = self.env["l10n_mx_edi.document"]

        esignature = (
            esignature
            or self.company_id.l10n_mx_edi_esignature_ids.get_valid_esignature()
        )
        certificate = esignature.get_cert_data()[1]
        private_key = esignature.get_pk_data()[1]

        for retry_count in range(max_retries):
            _logger.info(
                f"CFDI download request status verification... ({retry_count + 1}/{max_retries})"
            )
            if self.token_expiration < fields.Datetime.now():
                token_res = mx_edi_document.l10n_mx_ws_generate_token(
                    certificate, private_key
                )
                self.write(
                    {
                        "token": token_res["token"],
                        "token_expiration": datetime.fromisoformat(
                            token_res["expires"]
                        ),
                    }
                )
            verify_download = mx_edi_document.l10n_mx_ws_verify_package(
                certificate, private_key, self.token, self.request
            )
            self.write(
                {
                    "request_state": verify_download["estado_solicitud"],
                    "file_count": int(verify_download["numero_cfdis"]),
                    "request_message": verify_download["mensaje"],
                    "packages": (
                        verify_download["paquetes"][0]
                        if verify_download["paquetes"]
                        else ""
                    ),
                }
            )
            if int(self.request_state) > 2:
                break
            elif retry_count < max_retries - 1:  # avoid waiting in the last iteration
                _logger.info(f"Waiting {waiting_sec} seconds to retry...")
                time.sleep(waiting_sec)
                continue
        self.write({"count_verify": self.count_verify + 1})

    def action_download_cfdi(self, esignature=None):
        self.ensure_one()
        mx_edi_document = self.env["l10n_mx_edi.document"]
        docs_document = self.env["documents.document"]
        ir_attachment = self.env["ir.attachment"]

        esignature = (
            esignature
            or self.company_id.l10n_mx_edi_esignature_ids.get_valid_esignature()
        )
        certificate = esignature.get_cert_data()[1]
        private_key = esignature.get_pk_data()[1]

        document_ids = []

        if self.token_expiration < fields.Datetime.now():
            token_res = mx_edi_document.l10n_mx_ws_generate_token(
                certificate, private_key
            )
            self.write(
                {
                    "token": token_res["token"],
                    "token_expiration": datetime.fromisoformat(token_res["expires"]),
                }
            )

        download_res = mx_edi_document.l10n_mx_ws_download_package(
            certificate, private_key, self.token, self.packages
        )
        self.write(
            {
                "request_status_code": download_res["cod_estatus"],
                "request_message": download_res["mensaje"],
            }
        )
        if download_res["paquete_b64"]:
            content = download_res["paquete_b64"]
            folder_id = (
                self.company_id.l10n_mx_edi_folder.id or False
            )  # Precompute folder ID once

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
                        [("name", "in", names), ("company_id", "=", self.company_id.id)]
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
                                    "company_id": self.company_id.id,
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

        if document_ids:
            self.write({"document_ids": [(6, 0, document_ids)]})

        if not self.env.context.get("view_documents"):
            return False
        return self.action_view_documents()

    @api.model
    def _cron_sync_with_sat(self, company_id):
        now_mx = datetime.now(pytz.timezone(DEFAULT_TZ))
        param = self.env["ir.config_parameter"].sudo()
        hour_start = int(param.get_param("cfdi_cron.hour_start", 8))
        hour_end = int(param.get_param("cfdi_cron.hour_end", 18))
        current_hour = now_mx.hour

        if not (hour_start <= current_hour <= hour_end):
            _logger.info("not in time %s", hour_start)
            return
        is_first_run = current_hour == hour_start
        today = fields.Date.context_today(self.with_context(tz=DEFAULT_TZ))

        if is_first_run:
            _logger.info("is_first_run %s", is_first_run)
            date_from = (now_mx - timedelta(hours=24)).replace(
                minute=0, second=0, microsecond=0
            )
            _logger.info("date_from %s", date_from)
        else:
            date_from = (now_mx - timedelta(hours=2)).replace(
                minute=0, second=0, microsecond=0
            )

        date_to = now_mx.replace(minute=0, second=0, microsecond=0)
        _logger.info("date_to %s", date_to)
        existing_session = self.search(
            [
                ("company_id", "=", company_id),
                ("date_from", "=", date_from),
                ("date_to", "=", date_to),
            ],
            limit=1,
        )

        if existing_session:
            _logger.info(
                "Ya existe una sesión en ese rango de tiempo: ID %s",
                existing_session.id,
            )
            return

        context_with_dates = dict(self.env.context)
        context_with_dates.update(
            {
                "cron_date_from": fields.Datetime.to_string(date_from),
                "cron_date_to": fields.Datetime.to_string(date_to),
            }
        )
        self = self.with_context(context_with_dates)
        """Schedule action to check MX SAT sessions not closed or create new one if apply"""
        auto_commit = self.env.context.get("auto_commit", True)
        max_retries = self.env.context.get("max_retries", 5)
        waiting_sec = self.env.context.get("waiting_sec", 20)

        company = self.env["res.company"].browse(company_id)
        esignature = company.l10n_mx_edi_esignature_ids.get_valid_esignature()
        # 1. Sync with SAT (create token & send request)
        today = fields.Date.context_today(self.with_context(tz=DEFAULT_TZ))
        cron_user = self.env.ref("base.user_root")

        mx_session_today = self.create(
            {
                "name": today,
                "company_id": company_id,
            }
        )
        _logger.info("Was created a new MX session with ID %s", mx_session_today.id)
        try:
            mx_session_today.action_sync_with_sat(esignature)
        except Exception as e:
            if auto_commit:
                self.env.cr.rollback()
            _logger.error(e)
        finally:
            if auto_commit:
                self.env.cr.commit()  # pylint: disable=invalid-commit

        # 2. Verify
        max_verify_allowed = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("documents_l10n_mx_edi.default_max_verify_cfdi", "5")
        )
        domain_verify = [
            ("count_verify", "<=", max_verify_allowed),
            ("request_state", "in", ["1", "2"]),
            ("company_id", "=", company_id),
        ]
        mx_sessions_to_verify = self.search(domain_verify, order="id ASC")
        try:
            for mx_session_to_verify in mx_sessions_to_verify:
                mx_session_to_verify.action_verify_cfdi(
                    esignature, max_retries=max_retries, waiting_sec=waiting_sec
                )
                _logger.info(
                    "Was verified request for MX session with ID %s",
                    mx_session_to_verify.id,
                )
        except Exception as e:
            if auto_commit:
                self.env.cr.rollback()
            _logger.error(e)
        finally:
            if auto_commit:
                self.env.cr.commit()  # pylint: disable=invalid-commit

        # 3. Download
        domain_download = [
            ("request_status_code", "!=", "5008"),
            ("request_state", "=", "3"),
            ("company_id", "=", company_id),
            ("document_ids", "=", False),
        ]
        mx_sessions_to_download = self.search(domain_download, order="id ASC")
        try:

            for mx_session_to_download in mx_sessions_to_download:
                mx_session_to_download.action_download_cfdi(esignature)
                _logger.info(
                    "Was downloaded documents for MX session with ID %s",
                    mx_session_to_download.id,
                )
        except Exception as e:
            if auto_commit:
                self.env.cr.rollback()
            _logger.error(e)
        finally:
            if auto_commit:
                self.env.cr.commit()  # pylint: disable=invalid-commit

    def action_sync_with_sat(self, esignature):
        self.ensure_one()
        mx_edi_document = self.env["l10n_mx_edi.document"]
        certificate = esignature.get_cert_data()[1]
        private_key = esignature.get_pk_data()[1]
        three_days_ago = self.name - timedelta(days=3)
        date_from = self.env.context.get("cron_date_from")
        date_to = self.env.context.get("cron_date_to")
        token_res = mx_edi_document.l10n_mx_ws_generate_token(certificate, private_key)
        if date_from:
            date_from = fields.Datetime.to_datetime(date_from)
        else:
            three_days_ago = self.name - timedelta(days=3)
            date_from = fields.Datetime.to_datetime(three_days_ago)

        if date_to:
            date_to = fields.Datetime.to_datetime(date_to)
        else:
            date_to = fields.Datetime.to_datetime(self.name)

        _logger.info("date_from %s", date_from)
        _logger.info("date_to %s", date_to)
        self.write(
            {
                "token": token_res["token"],
                "token_expiration": datetime.fromisoformat(token_res["expires"]),
                "date_from": date_from,
                "date_to": date_to,
            }
        )
        request_res = mx_edi_document.l10n_mx_ws_request_download(
            certificate,
            private_key,
            self.token,
            {"date_from": date_from, "date_to": date_to},
        )
        self.write(
            {
                "request": request_res["id_solicitud"],
                "request_status_code": request_res["cod_estatus"],
                "request_message": request_res["mensaje"],
                "request_state": "1" if request_res["cod_estatus"] == "5000" else "0",
            }
        )

    def action_view_documents(self):
        action = self.env.ref("documents.document_action").read()[0]
        action["domain"] = [("id", "in", self.document_ids.ids)]
        return action
