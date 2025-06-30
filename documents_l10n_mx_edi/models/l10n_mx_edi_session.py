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
    request_type = fields.Selection(
        selection=[
            ("CFDI", "CFDI"),
            ("Metadata", "Metadata"),
        ],
        default="CFDI",
    )
    request_mode = fields.Selection(
        selection=[
            ("playwright", "Playwright"),
            ("api", "API"),
        ],
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                company_id = vals.get("company_id") or self.env.company.id
                sequence_code = "sat.session"
                name = self.env["ir.sequence"].with_company(company_id).next_by_code(sequence_code)
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

        esignature = esignature or self.company_id.l10n_mx_edi_esignature_ids.get_valid_esignature()

        certificate = esignature.get_cert_data()[1]
        private_key = esignature.get_pk_data()[1]
        try:
            token_res = mx_edi_document.l10n_mx_ws_generate_token(certificate, private_key)
            self.write(
                {
                    "token": token_res["token"],
                    "token_expiration": datetime.fromisoformat(token_res["expires"]),
                }
            )
        except Exception as e:
            self.message_post(body=self.env._("Token generation error: %s") % str(e))
            return

        try:
            # 1. First attempt with Playwright
            request_res = mx_edi_document.l10n_mx_ws_request_download_playwright(
                esignature, self.date_from, self.date_to, self.request_type
            )
            request_mode = "playwright"

        except Exception as e_playwright:
            # 2. Fallback to standard web service
            _logger.warning("Playwright request failed: %s. Falling back to SAT web service.", e_playwright)
            try:
                request_res = mx_edi_document.l10n_mx_ws_request_download(
                    certificate,
                    private_key,
                    self.token,
                    {
                        "date_from": self.date_from,
                        "date_to": self.date_to,
                        "cfdi_state": "Vigente",
                        "request_type": self.request_type,
                    },
                )
                request_mode = "api"
            except Exception as e_ws:
                # If both methods fail, post the final error and stop.
                _logger.error("Standard web service request also failed.", exc_info=True)
                error_message = self.env._(
                    "Both browser automation and the standard web service failed.\n\n"
                    "Browser automation error: %s\n\nStandard web service error: %s",
                    str(e_playwright),
                    str(e_ws),
                )
                self.message_post(body=error_message)
                self.write({"request_state": "4"})  # Set state to Error
                return

        self.write(
            {
                "request": request_res["request_id"],
                "request_status_code": request_res["status_code"],
                "request_message": request_res["message"],
                "request_state": "1" if request_res["status_code"] == "5000" else "0",
                "request_mode": request_mode,
            }
        )

    def action_verify_cfdi(self, esignature=None, max_retries=2, waiting_sec=0):
        self.ensure_one()

        mx_edi_document = self.env["l10n_mx_edi.document"]

        esignature = esignature or self.company_id.l10n_mx_edi_esignature_ids.get_valid_esignature()

        certificate = esignature.get_cert_data()[1]
        private_key = esignature.get_pk_data()[1]

        for retry_count in range(max_retries):
            _logger.info(
                "CFDI download request status verification... (%s/%s)",
                (retry_count + 1),
                max_retries,
            )
            if self.token_expiration < fields.Datetime.now():
                token_res = mx_edi_document.l10n_mx_ws_generate_token(certificate, private_key)
                self.write(
                    {
                        "token": token_res["token"],
                        "token_expiration": datetime.fromisoformat(token_res["expires"]),
                    }
                )
            verify_download = mx_edi_document.l10n_mx_ws_verify_package(
                certificate, private_key, self.token, self.request
            )
            _logger.info("Verification response %s", verify_download)
            self.write(
                {
                    "request_state": verify_download["estado_solicitud"],
                    "file_count": int(verify_download["numero_cfdis"]),
                    "request_message": verify_download["mensaje"],
                    "packages": (verify_download["paquetes"][0] if verify_download["paquetes"] else ""),
                }
            )
            # self.write(
            #    {
            #        "request_state": verify_download["request_status"],
            #        "file_count": int(verify_download["cfdi_count"]),
            #        "request_message": verify_download["message"],
            #        "packages": (verify_download["packages"][0] if verify_download["packages"] else ""),
            #    }
            # )
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
        esignature = esignature or self.company_id.l10n_mx_edi_esignature_ids.get_valid_esignature()
        if not esignature:
            self.message_post(body=self.env._("No valid electronic signature found"))
            return

        certificate = esignature.get_cert_data()[1]
        private_key = esignature.get_pk_data()[1]

        # Renew token if expired
        if not self.token or self.token_expiration < fields.Datetime.now():
            try:
                token_res = mx_edi_document.l10n_mx_ws_generate_token(certificate, private_key)
                self.write(
                    {
                        "token": token_res["token"],
                        "token_expiration": datetime.fromisoformat(token_res["expires"]),
                    }
                )
            except Exception as e:
                self.message_post(body=self.env._("Token generation error: %s") % str(e))
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
            self.message_post(body=self.env._("No content found in the downloaded package"))
            return

        content = download_res["paquete_b64"]
        folder_id = self.company_id.l10n_mx_edi_folder.id or False  # Precompute folder ID once

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
                self.message_post(body=self.env._("No valid XML files found for processing."))
                return

            existing_docs = docs_document
            for fname, normalized_fname in xml_files:
                duplicity_result = mx_edi_document._get_duplicate_cfdi(fname, docs_document)

                if duplicity_result["duplicated"]:
                    existing_docs |= duplicity_result["document"]
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
                self.message_post(body=self.env._("No valid XML files found for processing."))
                return

            # Bulk create records if we have valid files
            try:
                # Create all attachments in single operation
                attachments = ir_attachment.with_context(force_l10n_mx_edi_cfdi_uuid=True).create(att_vals_list)

                # Prepare documents to create
                created_documents = docs_document
                if doc_vals_list:
                    # Assign attachment IDs to corresponding documents
                    for attachment, doc_vals in zip(attachments, doc_vals_list):
                        doc_vals["attachment_id"] = attachment.id

                    # Bulk create all documents
                    created_documents = docs_document.create(doc_vals_list)

                session_docs = created_documents | existing_docs

                # Update documents into session
                if session_docs:
                    self.write({"document_ids": [(6, 0, session_docs.ids)]})

                created_items = (
                    "".join([f"<li>{doc.name} (ID: {doc.id})</li>" for doc in created_documents]) or "<li>None</li>"
                )

                existing_items = (
                    "".join([f"<li>{doc.name} (ID: {doc.id})</li>" for doc in existing_docs]) or "<li>None</li>"
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
                    <p><b>Previously existing documents ({len(existing_docs)}):</b></p>
                    <ul>
                        {existing_items}
                    </ul>

                    <p><b>Total processed documents:</b> {len(session_docs)}</p>
                </div>
                """
                )

                # Send summary message
                self.message_post(body=summary_message)
                _logger.info(
                    "Downloaded %s documents for MX session ID %s",
                    len(session_docs),
                    self.id,
                )

            except Exception as e:
                error_message = self.env._("Document processing error: %s") % str(e)
                self.message_post(body=error_message)
                _logger.warning(error_message)

    @api.model
    def _generate_time_blocks(self, company_id):
        """Create scheduled sessions, handling gaps, rejections, and stuck sessions.

        This method implements a robust logic to avoid time gaps:
        1. It checks the last two sessions to detect complex states.
        2. If a session is 'Finished' or 'Rejected' but its predecessor is stuck
        'To Verify', it consolidates the time range of both into a new session.
        3. If two consecutive sessions are 'To Verify', it treats them as stuck,
        rejects them, and creates a new session covering their entire period.
        4. If a session was 'Rejected', it retries that time block.
        5. If everything is clear, it proceeds to the next time block.

        Args:
            company_id (int): ID of the company to create sessions for.

        Returns:
            recordset: New sessions created for processing.
        """
        user_root = self.env.ref("base.user_root")

        # Timezone setup
        mexico_tz = pytz.timezone(DEFAULT_TZ)
        utc_tz = pytz.UTC
        now_utc = datetime.now(utc_tz)
        now_mx = now_utc.astimezone(mexico_tz)
        today = now_mx.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = today

        # Get the last two sessions to understand the state of the queue
        sessions = self.search(
            [
                ("company_id", "=", company_id),
                ("create_uid", "=", user_root.id),
            ],
            order="date_to desc, id desc",
            limit=2,
        )
        last_session = sessions and sessions[0] or self.browse()
        previous_session = len(sessions) > 1 and sessions[1] or self.browse()

        # Default start date is yesterday, used if no history exists.
        start_date = today - timedelta(days=1)

        # Determine the status of the last two sessions
        last_is_verifying = last_session and last_session.request_state in ["0", "1", "2"]
        prev_is_verifying = previous_session and previous_session.request_state in ["0", "1", "2"]

        # --- State Evaluation Logic ---
        if prev_is_verifying:
            # Scenario 1: Both sessions are stuck verifying. Reject both.
            if last_is_verifying:
                _logger.warning(
                    "Company %d: Found two consecutive 'To Verify' sessions (IDs: %s, %s). "
                    "Forcing rejection on both to clear the blockage.",
                    company_id,
                    previous_session.id,
                    last_session.id,
                )
                start_date = previous_session.date_from.astimezone(mexico_tz)
                (previous_session | last_session).write(
                    {
                        "request_state": "6",
                        "state_msg": "Forcibly rejected by cron due to consecutive pending sessions.",
                    }
                )
            # Scenario 2: Only the previous session is stuck. Reject only that one.
            else:
                _logger.warning(
                    "Company %d: Previous session (ID %d) is 'To Verify' while the last session (ID %s) is not. "
                    "Rejecting the orphaned session to fill the data gap.",
                    company_id,
                    previous_session.id,
                    last_session.id,
                )
                start_date = previous_session.date_from.astimezone(mexico_tz)
                previous_session.write(
                    {
                        "request_state": "6",
                        "state_msg": "Forcibly rejected by cron to consolidate a prior stuck session.",
                    }
                )
        elif last_session:
            # Scenario 3: Previous session is clean, evaluate the last session.
            if last_is_verifying:
                # "Create the next one": Start the new block after the one being verified.
                # The main cron loop will continue to attempt verification on the pending session.
                _logger.info(
                    "Company %d: Last session (ID %d) is 'To Verify'. Creating next time block while verification continues.",
                    company_id,
                    last_session.id,
                )
                start_date = last_session.date_to.astimezone(mexico_tz)
            elif last_session.request_state in ["4", "5", "6"]:
                _logger.info(
                    "Company %d: Last session (ID %d) was 'Rejected'. Retrying this time block.",
                    company_id,
                    last_session.id,
                )
                start_date = last_session.date_from.astimezone(mexico_tz)
            else:  # Assumed '3' (Finished)
                start_date = last_session.date_to.astimezone(mexico_tz)

        # --- Session Creation Loop ---
        current_date = start_date
        new_sessions = self.browse()

        # The cron docstring mentions 2-hour blocks.
        while current_date < end_date:
            next_date = min(end_date, current_date + timedelta(days=1))

            # Convert to UTC and remove tzinfo for database storage
            date_from_utc = current_date.astimezone(utc_tz).replace(tzinfo=None)
            date_to_utc = next_date.astimezone(utc_tz).replace(tzinfo=None)

            # Check if an identical session already exists to avoid duplicates
            if not self.search_count(
                [
                    ("date_from", "=", date_from_utc),
                    ("date_to", "=", date_to_utc),
                    ("company_id", "=", company_id),
                    ("create_uid", "=", user_root.id),
                ]
            ):
                new_session = self.create(
                    {
                        "company_id": company_id,
                        "date_from": date_from_utc,
                        "date_to": date_to_utc,
                    }
                )
                new_sessions += new_session

            current_date = next_date

        if new_sessions:
            _logger.info("Company %d: Created %d new session(s) to process.", company_id, len(new_sessions))

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
            self.env["ir.config_parameter"].sudo().get_param("documents_l10n_mx_edi.default_max_verify_cfdi", "5")
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
        companies = self.env["res.company"].search([("l10n_mx_edi_certificate_ids", "!=", False)])
        valid_companies = companies.filtered(
            lambda c: any(
                (cert.date_start.date() if isinstance(cert.date_start, datetime) else cert.date_start)
                <= today
                <= (cert.date_end.date() if isinstance(cert.date_end, datetime) else cert.date_end)
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
                    session_to_verify.action_verify_cfdi(esignature, max_retries=max_retries, waiting_sec=waiting_sec)
                # 4. Download CFDIs
                sessions_to_download = self._get_download_candidates(company.id)
                for session_to_download in sessions_to_download:
                    session_to_download.action_download_cfdi(esignature)
            except Exception as e:
                if auto_commit:
                    self.env.cr.rollback()
                _logger.error("Error processing sessions for company %s: %s", company.name, e)
            finally:
                if auto_commit:
                    self.env.cr.commit()  # pylint: disable=invalid-commit
