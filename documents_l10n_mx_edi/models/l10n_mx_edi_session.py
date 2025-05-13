import base64
import io
import logging
import os
import time
import zipfile
from datetime import datetime, timedelta

import pytz
from markupsafe import Markup

from odoo import api, fields, models
from odoo.osv import expression

from .l10n_mx_edi_document import MXWS_ERROR_TYPE

DEFAULT_TZ = "America/Mexico_City"

_logger = logging.getLogger(__name__)


class Session(models.Model):
    _name = "l10n_mx_edi.session"
    _inherit = ["mail.thread"]
    _description = "MX SAT session"
    _order = "create_date desc"

    name = fields.Char(required=True, copy=False, readonly=True, default="/")
    company_id = fields.Many2one(
        "res.company",
        "Company",
        default=lambda self: self.env.company,
        readonly=True,
    )
    uuid = fields.Char("UUID", readonly=True, copy=False)
    token = fields.Char(readonly=True, copy=False)
    token_expiration = fields.Datetime(readonly=True, copy=False)
    date_from = fields.Datetime("Date from", required=True)
    date_to = fields.Datetime("Date to", required=True)
    request = fields.Char("Request ID", readonly=True, copy=False)
    request_status_code = fields.Char("Request code", readonly=True, copy=False)
    request_state = fields.Selection(
        MXWS_ERROR_TYPE,
        "Request state",
        default="0",
        required=True,
        readonly=True,
        copy=False,
    )
    request_message = fields.Char("Request message", readonly=True, copy=False)
    file_count = fields.Integer("File count", readonly=True, copy=False)
    packages = fields.Char("packages", readonly=True, copy=False)
    document_ids = fields.Many2many(
        "documents.document",
        "document_l10n_mx_edi_session_rel",
        "l10n_mx_edi_session_id",
        "document_id",
        string="Documents",
        readonly=True,
        copy=False,
    )
    count_verify = fields.Integer(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                company_id = vals.get("company_id") or self.env.company.id
                sequence_code = "sat.session"
                name = (
                    self.env["ir.sequence"]
                    .with_company(company_id)
                    .next_by_code(sequence_code)
                )
                if not name:
                    sequence = (
                        self.env["ir.sequence"]
                        .sudo()
                        .create(
                            {
                                "name": self.env._("L10n MX EDI Session Sequence"),
                                "code": sequence_code,
                                "prefix": "SAT/SESSION/%(y)s/%(month)s/",
                                "padding": 4,
                                "company_id": company_id,
                            }
                        )
                    )
                    name = sequence.next_by_id()
                vals["name"] = name
        return super().create(vals_list)

    def get_mx_current_datetime(self):
        return fields.Datetime.context_timestamp(
            self.with_context(tz="America/Mexico_City"), fields.Datetime.now()
        )

    def action_request_cfdi(self, esignature=None):
        """Request CFDI download from SAT by a given date range.

        Args:
            esignature (record): Electronic signature record with certificate data

        Raises:
            UserError: If dates are missing or invalid
            Exception: For any SAT communication errors
        """
        self.ensure_one()
        mx_edi_document = self.env["l10n_mx_edi.document"]

        esignature = (
            esignature
            or self.company_id.l10n_mx_edi_esignature_ids.get_valid_esignature()
        )

        certificate = esignature.get_cert_data()[1]
        private_key = esignature.get_pk_data()[1]
        token_res = mx_edi_document.l10n_mx_ws_generate_token(certificate, private_key)
        self.write(
            {
                "token": token_res["token"],
                "token_expiration": datetime.fromisoformat(token_res["expires"]),
            }
        )
        request_res = mx_edi_document.l10n_mx_ws_request_download(
            certificate,
            private_key,
            self.token,
            {"date_from": self.date_from, "date_to": self.date_to},
        )
        self.write(
            {
                "request": request_res["id_solicitud"],
                "request_status_code": request_res["cod_estatus"],
                "request_message": request_res["mensaje"],
                "request_state": "1" if request_res["cod_estatus"] == "5000" else "0",
            }
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
                "CFDI download request status verification... (%s/%s)",
                (retry_count + 1),
                max_retries,
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
            if retry_count < max_retries - 1:  # avoid waiting in the last iteration
                _logger.info("Waiting %s seconds to retry...", waiting_sec)
                time.sleep(waiting_sec)
                continue
        self.write({"count_verify": self.count_verify + 1})
        _logger.info("Was verified request for MX session with ID %s", self.id)

    def action_download_cfdi(self, esignature=None):
        self.ensure_one()
        mx_edi_document = self.env["l10n_mx_edi.document"]
        docs_document = self.env["documents.document"]
        ir_attachment = self.env["ir.attachment"]

        # Get valid electronic signature
        esignature = (
            esignature
            or self.company_id.l10n_mx_edi_esignature_ids.get_valid_esignature()
        )
        if not esignature:
            self.message_post(body=self.env._("No valid electronic signature found"))
            return

        certificate = esignature.get_cert_data()[1]
        private_key = esignature.get_pk_data()[1]

        document_ids = []

        # Renew token if expired
        if not self.token or self.token_expiration < fields.Datetime.now():
            try:
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
            except Exception as e:
                self.message_post(
                    body=self.env._("Token generation error: %s") % str(e)
                )
                return

        # Download the package from the web service
        try:
            download_res = mx_edi_document.l10n_mx_ws_download_package(
                certificate, private_key, self.token, self.packages
            )
            self.write(
                {
                    "request_status_code": download_res["cod_estatus"],
                    "request_message": download_res["mensaje"],
                }
            )
        except Exception as e:
            self.message_post(body=self.env._("Package download error: %s") % str(e))
            return

        # Process the downloaded package if it exists
        if download_res.get("paquete_b64") is None:
            self.message_post(
                body=self.env._("No content found in the downloaded package")
            )
            return

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
                (fname, os.path.splitext(fname)[0].upper() + ".xml")
                for fname in container.namelist()
                if fname.lower().endswith(".xml")
            ]

            if not xml_files:
                self.message_post(
                    body=self.env._("No valid XML files found for processing.")
                )
                return

            # Preparing domain
            domain = expression.AND(
                [
                    [("company_id", "in", [False, self.company_id.id])],
                    expression.OR(
                        [
                            [("name", "=ilike", fname)]
                            for fname, normalized_fname in xml_files
                        ]
                    ),
                ]
            )

            # Find all existing documents
            existing_docs = docs_document.sudo().search(
                domain, order="name asc, id asc"
            )

            # Ensure uniqueness
            unique_existing_docs = docs_document
            for doc in existing_docs:
                doc_name = doc.name.split(".")[0].upper() + ".xml"
                if doc_name not in unique_existing_docs.mapped("name"):
                    unique_existing_docs += doc

            # Existing documents are kept for return
            document_ids.extend(unique_existing_docs.ids)

            # already processed files
            existing_names = unique_existing_docs.mapped("name")

            for fname, normalized_fname in xml_files:

                if normalized_fname in existing_names:
                    continue  # Skip already processed files

                with container.open(fname) as file:
                    file_raw = file.read()
                    file_content = base64.b64encode(file_raw)

                    if not mx_edi_document._l10n_mx_edi_is_cfdi(file_raw):
                        continue  # Skip non-CFDI XMLs

                    # Prepare for batch creation
                    att_vals_list.append(
                        {
                            "name": normalized_fname,
                            "type": "binary",
                            "datas": file_content,
                            "mimetype": "text/plain",  # to be able to open file from documents
                        }
                    )
                    doc_vals_list.append(
                        {
                            "name": normalized_fname,
                            "folder_id": folder_id,
                            "company_id": self.company_id.id,
                            "l10n_mx_edi_is_cfdi": True,
                        }
                    )

            # If there are no new documents to create and no existing ones, we return
            if not doc_vals_list and not existing_docs:
                self.message_post(
                    body=self.env._("No valid XML files found for processing.")
                )
                return

            # Bulk create records if we have valid files
            try:
                # Create all attachments in single operation
                attachments = ir_attachment.with_context(
                    force_l10n_mx_edi_cfdi_uuid=True
                ).create(att_vals_list)

                # Prepare documents to create
                created_documents = docs_document
                if doc_vals_list:
                    # Assign attachment IDs to corresponding documents
                    for attachment, doc_vals in zip(attachments, doc_vals_list):
                        doc_vals["attachment_id"] = attachment.id

                    # Bulk create all documents
                    created_documents = docs_document.create(doc_vals_list)

                document_ids.extend(created_documents.ids)

                # Update documents into session
                if document_ids:
                    self.write({"document_ids": [(6, 0, document_ids)]})

                created_items = (
                    "".join(
                        [
                            f"<li>{doc.name} (ID: {doc.id})</li>"
                            for doc in created_documents
                        ]
                    )
                    or "<li>None</li>"
                )

                existing_items = (
                    "".join(
                        [
                            f"<li>{doc.name} (ID: {doc.id})</li>"
                            for doc in unique_existing_docs
                        ]
                    )
                    or "<li>None</li>"
                )

                # Prepare summary message
                summary_message = Markup(
                    f"""
                <div class="o_mail_note">
                    <h4>Document Processing Summary</h4>
                    <p><b>Newly created documents ({len(created_documents)}):</b></p>
                    <ul>
                        {created_items}
                    </ul>
                    <p><b>Previously existing documents ({len(unique_existing_docs)}):</b></p>
                    <ul>
                        {existing_items}
                    </ul>

                    <p><b>Total processed documents:</b> {len(document_ids)}</p>
                </div>
                """
                )

                # Send summary message
                self.message_post(body=summary_message)
                _logger.info(
                    "Downloaded %s documents for MX session ID %s",
                    len(document_ids),
                    self.id,
                )

            except Exception as e:
                error_message = self.env._("Document processing error: %s") % str(e)
                self.message_post(body=error_message)
                _logger.warning(error_message)

    @api.model
    def _get_next_time_block(self, current_time, time_blocks, hour_start, timezone):
        """Calculate the next time block based on current time.

        Args:
            current_time (datetime): Current time in Mexico timezone
            time_blocks (list): List of time block tuples (start_hour, end_hour)
            hour_start (int): Starting hour for operations
            timezone: Mexico timezone object

        Returns:
            datetime: Next time block in Mexico timezone
        """
        current_day = current_time.replace(hour=0, minute=0, second=0, microsecond=0)

        for start_hour, end_hour in time_blocks:
            if current_time.hour < start_hour:
                return current_day.replace(hour=start_hour)
            if start_hour <= current_time.hour < end_hour:
                return current_day.replace(hour=end_hour)

        # If after last block, move to next day
        return (current_day + timedelta(days=1)).replace(hour=hour_start)

    @api.model
    def _generate_time_blocks(self, company_id):
        """Create scheduled sessions for a specific company in 2-hour blocks.

        Args:
            company_id (int): ID of the company to create sessions for

        Returns:
            list: IDs of created sessions or False if outside operating hours
        """
        # Timezone setup
        mexico_tz = pytz.timezone(DEFAULT_TZ)
        utc_tz = pytz.UTC
        now_utc = datetime.now(utc_tz)
        now_mx = now_utc.astimezone(mexico_tz)

        # Get operating hours from system parameters
        icp = self.env["ir.config_parameter"].sudo()
        hour_start = int(
            icp.get_param("documents_l10n_mx_edi.hour_start_download_cfdi", "8")
        )
        hour_end = int(
            icp.get_param("documents_l10n_mx_edi.hour_end_download_cfdi", "18")
        )
        hour_interval = int(
            icp.get_param("documents_l10n_mx_edi.hour_interval_download_cfdi", "2")
        )

        # Check if within operating hours
        if not hour_start <= now_mx.hour <= hour_end:
            _logger.info(
                "Outside operating hours: current %s, allowed range: %s-%s",
                now_mx.hour,
                hour_start,
                hour_end,
            )
            return False

        # Get last session or default to 7 days ago
        last_session = self.search(
            [("company_id", "=", company_id)], order="date_to desc", limit=1
        )
        start_date = (
            last_session.date_to.astimezone(mexico_tz)
            if last_session and last_session.date_to
            else now_mx - timedelta(days=7)
        )
        # Generate time blocks (2-hour intervals)
        time_blocks = [
            (hour, hour + hour_interval)
            for hour in range(hour_start, hour_end, hour_interval)
        ]

        # Calculate end time (current hour rounded down)
        today = now_mx.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = now_mx.replace(minute=0, second=0, microsecond=0)

        # Adjust end time if outside operating hours
        if now_mx.hour < hour_start:
            end_time = today.replace(hour=hour_start)
        elif now_mx.hour >= hour_end:
            end_time = today.replace(hour=hour_end)

        # Create sessions in 2-hour blocks
        current_time = start_date
        new_sessions = self

        while current_time < end_time:
            # Find next time block
            next_time = self._get_next_time_block(
                current_time, time_blocks, hour_start, mexico_tz
            )

            if next_time > end_time:
                break

            # Create session if doesn't exist
            date_from_utc = current_time.astimezone(utc_tz).replace(tzinfo=None)
            date_to_utc = next_time.astimezone(utc_tz).replace(tzinfo=None)

            existing_session = self.search(
                [
                    ("date_from", "=", date_from_utc),
                    ("date_to", "=", date_to_utc),
                    ("company_id", "=", company_id),
                ],
                limit=1,
            )
            if not existing_session:
                new_sessions += self.create(
                    {
                        "company_id": company_id,
                        "date_from": date_from_utc,
                        "date_to": date_to_utc,
                    }
                )

            current_time = next_time

        return new_sessions

    @api.model
    def _get_verify_candidates(self, company_id):
        """Retrieve active sessions eligible for verification (within max attempts limit).

        Filters sessions that:
        - Belong to the specified company
        - Are in states: '0' (Pending), '1' (Processing), or '2' (Verifying)
        - Haven't exceeded the max verification attempts configured in system parameters

        Args:
            company_id (int): Target company ID

        Returns:
            recordset: Sessions ready for verification, ordered by oldest first
        """
        max_verify_allowed = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("documents_l10n_mx_edi.default_max_verify_cfdi", "5")
        )

        return self.search(
            [
                ("company_id", "=", company_id),
                ("request_state", "in", ["1", "2"]),
                ("count_verify", "<=", max_verify_allowed),
            ],
            order="date_from asc",
        )

    @api.model
    def _get_download_candidates(self, company_id):
        """Retrieve completed sessions ready for CFDI download

        Args:
            company_id (int): Target company ID

        Returns:
            recordset: Sessions ready for download, ordered by ID ascending
        """
        domain = [
            ("request_status_code", "!=", "5008"),  # Exclude "not found" errors
            ("request_state", "=", "3"),  # Only completed sessions
            ("company_id", "=", company_id),  # Filter by company
            ("document_ids", "=", False),  # Only no documents downloaded
        ]
        return self.search(domain, order="id ASC")

    @api.model
    def _cron_sync_with_sat(self):
        """Create scheduled sessions in 2-hour blocks and process active sessions.

        This method:
        1. Creates necessary sessions for all companies in 2-hour blocks
        2. Processes sessions (request, verification and document download)

        """
        auto_commit = self.env.context.get("auto_commit", True)
        max_retries = self.env.context.get("max_retries", 2)
        waiting_sec = self.env.context.get("waiting_sec", 0)
        today = datetime.now().date()
        companies = self.env["res.company"].search(
            [("l10n_mx_edi_certificate_ids", "!=", False)]
        )
        valid_companies = companies.filtered(
            lambda c: any(
                (
                    cert.date_start.date()
                    if isinstance(cert.date_start, datetime)
                    else cert.date_start
                )
                <= today
                <= (
                    cert.date_end.date()
                    if isinstance(cert.date_end, datetime)
                    else cert.date_end
                )
                for cert in c.l10n_mx_edi_certificate_ids
            )
        )
        for company in valid_companies:
            esignature = company.l10n_mx_edi_esignature_ids.get_valid_esignature()
            try:
                # 1. Generate sessions
                new_sessions = self._generate_time_blocks(company.id)
                # 2. Create token & send a request download
                for session_to_request in new_sessions:
                    session_to_request.action_request_cfdi(esignature)
                # 3. Verify request
                sessions_to_verify = self._get_verify_candidates(company.id)
                for session_to_verify in sessions_to_verify:
                    session_to_verify.action_verify_cfdi(
                        esignature, max_retries=max_retries, waiting_sec=waiting_sec
                    )
                # 4. Download CFDIs
                sessions_to_download = self._get_download_candidates(company.id)
                for session_to_download in sessions_to_download:
                    session_to_download.action_download_cfdi(esignature)
            except Exception as e:
                if auto_commit:
                    self.env.cr.rollback()
                _logger.error(
                    "Error processing sessions for company %s: %s", company.name, e
                )
            finally:
                if auto_commit:
                    self.env.cr.commit()  # pylint: disable=invalid-commit
