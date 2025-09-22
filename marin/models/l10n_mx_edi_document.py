import logging

from datetime import datetime, timedelta
from requests.exceptions import ConnectTimeout, HTTPError, RequestException
from zeep import Client, Transport

from odoo import api, fields, models, tools

_logger = logging.getLogger(__name__)


class L10nMxEdiDocument(models.Model):
    _inherit = "l10n_mx_edi.document"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    last_sat_state_sync_date = fields.Datetime(
        string="Last SAT Status Sync",
        default=fields.Datetime.now,
        readonly=True,
    )

    def _fetch_sat_status(self, supplier_rfc, customer_rfc, total, uuid):
        """Override the SAT web service to check the status of an electronic invoice to implement EstadoCancelacion

        Args:
            supplier_rfc (str): Tax ID of the supplier/issuer
            customer_rfc (str): Tax ID of the customer/receiver
            total (float): Total amount of the invoice
            uuid (str): Unique identifier of the invoice (Folio Fiscal)

        Returns:
            dict: A dictionary containing:
                - 'value': Status of the invoice ('valid', 'cancelled', 'not_found', 'not_defined', or 'error')
                - 'error': (optional) Error message if the query fails
        """
        # SAT web service endpoint
        url = "https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc?wsdl"

        # Build query parameters with proper escaping and default values
        params = (
            f'?id={uuid or ""}'
            f'&re={tools.html_escape(supplier_rfc or "")}'
            f'&rr={tools.html_escape(customer_rfc or "")}'
            f"&tt={total or 0.0}"
        )

        # Configure transport with timeout to avoid hanging
        transport = Transport(timeout=20)

        try:
            # Create SOAP client and make the query
            client = Client(wsdl=url, transport=transport)
            response = client.service.Consulta(params)

            # Extract relevant status information from response
            fetched_state = response["Estado"] if hasattr(response, "Estado") else ""
            fetched_cancel_state = (
                response["EstadoCancelacion"]
                if hasattr(response, "EstadoCancelacion")
                else ""
            )

        except Exception as e:
            # Return error information if the query fails
            return {
                "error": self.env._(
                    "Failure during update of the SAT status: %s", str(e)
                ),
                "value": "error",
            }

        # Determine the invoice status based on SAT response
        if fetched_state == "Vigente":
            # Even if state is 'Vigente', check cancellation status
            if fetched_cancel_state not in (None, "", "None"):
                return {"value": "cancelled"}
            return {"value": "valid"}
        elif fetched_state == "Cancelado":
            return {"value": "cancelled"}
        elif fetched_state == "No Encontrado":
            return {"value": "not_found"}
        else:
            # For any other unexpected state
            return {"value": "not_defined"}

    @api.model
    def _get_update_sat_status_domains(self, from_cron=True):
        """Override to ensure that can be handle cases from valid to cancel, also treatment filter"""
        base_domains = [
            [
                ("state", "in", ("ginvoice_sent", "ginvoice_cancel")),
                (
                    "invoice_ids",
                    "any",
                    [("l10n_mx_edi_cfdi_state", "=", "global_sent")],
                ),
            ],  # Global invoices
            [
                (
                    "state",
                    "in",
                    (
                        "invoice_sent",
                        "invoice_cancel_requested",
                        "invoice_cancel",
                        "invoice_received",
                    ),
                ),
                (
                    "move_id.l10n_mx_edi_cfdi_state",
                    "in",
                    ("sent", "cancel_requested", "cancel", "received"),
                ),
                (
                    "move_id.journal_id.x_treatment",
                    "in",
                    ("fiscal_real", "fiscal_simulated"),
                ),
            ],  # Regular invoices
            [
                ("state", "in", ("picking_sent", "picking_cancel")),
                (
                    "picking_id.l10n_mx_edi_cfdi_state",
                    "in",
                    ("sent", "cancel_requested", "cancel", "received"),
                ),
            ],  # Carta Porte
        ]

        # Main filter
        sat_state_filter = [("sat_state", "not in", ("cancelled", "skip"))]

        # Add main filter to each subdomain
        results = []
        for domain in base_domains:
            combined = domain + sat_state_filter
            results.append(combined)
        return results

    @api.model
    def _fetch_and_update_sat_status(self, batch_size=None, extra_domain=None):
        """Override fetch and update SAT status for documents with robust transaction handling.

        :param int batch_size: Number of documents to process in this batch
        :param list extra_domain: Additional domain filters
        :return: None
        """
        ir_config = self.env["ir.config_parameter"].sudo()
        sat_cancellations_channel = self.env.ref(
            "marin.sat_status_cancellation_channel"
        )
        batch_size = batch_size or int(
            ir_config.get_param("l10n_mx_edi_marin.sat_batch_size", default=100)
        )
        max_days = int(
            ir_config.get_param("l10n_mx_edi_marin.sat_status_max_days", default=60)
        )
        extra_domain = extra_domain or []

        start_date = datetime.today() - timedelta(days=max_days)
        extra_domain.append(("create_date", ">=", start_date.strftime("%Y-%m-%d")))
        domain = self._get_update_sat_status_domain(extra_domain=extra_domain)

        documents = self.search(
            domain, limit=batch_size, order="last_sat_state_sync_date, id"
        )
        sync_date = fields.Datetime.now()
        auto_commit = self.env.context.get("auto_commit", True)
        processed_documents = self.browse()

        for document in documents:
            invoice = document.move_id
            last_sat_state = invoice.l10n_mx_edi_cfdi_sat_state
            try:
                document._update_sat_state()
                if auto_commit:
                    self.env.cr.commit()
            except (ConnectTimeout, HTTPError, RequestException) as error:
                # Network/SAT service errors - propagate to trigger retry mechanism
                _logger.info(
                    "Network error occurred while updating SAT status for document %s. "
                    "Operation will be retried later.",
                    invoice.name,
                )
                raise

            except Exception as error:
                # Business errors - log and continue with next document
                _logger.warning(
                    "Business error occurred while updating SAT status for document %s. "
                    "Skipping document and moving to next one.",
                    invoice.name,
                    exc_info=True,
                )
                self.env.cr.rollback()
                continue

            processed_documents |= document

            # Recently cancelled
            if (
                last_sat_state == "valid"
                and invoice.l10n_mx_edi_cfdi_sat_state == "cancelled"
            ):
                message = invoice._get_sat_status_cancellation_message()
                # Post message to the cancellation channel
                sat_cancellations_channel.message_post(
                    body=message,
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                )

        processed_documents.write({"last_sat_state_sync_date": sync_date})
