from odoo import models, api, tools, _
from odoo.osv import expression
from datetime import datetime, timedelta
from zeep import Client, Transport
import logging

_logger = logging.getLogger(__name__)


class L10nMxEdiDocument(models.Model):
    _inherit = "l10n_mx_edi.document"

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
            fetched_cancel_state = response["EstadoCancelacion"] if hasattr(response, "EstadoCancelacion") else ""

        except Exception as e:
            # Return error information if the query fails
            return {
                "error": _("Failure during update of the SAT status: %s", str(e)),
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

        base_domains = super()._get_update_sat_status_domains(from_cron=from_cron)

        treatment_filter = [
            (
                "move_id.journal_id.x_treatment",
                "in",
                ("fiscal_real", "fiscal_simulated"),
            )
        ]
        new_domain = []
        for domain in base_domains:
            combined = expression.AND([domain, treatment_filter])
            new_domain.append(combined)

        return new_domain

    def _get_sat_status_cancellation_message(self):
        """Generate the message body for cancellation notification."""
        self.ensure_one()
        message = f"""
        <div class="o_mail_notification">
            <strong>Cancelación Detectada en SAT</strong><br/>
            <strong>Factura:</strong> {self.name or 'N/A'}<br/>
            <strong>Folio Fiscal:</strong> {self.l10n_mx_edi_cfdi_uuid or 'N/A'}<br/>
            <strong>Cliente:</strong> {self.partner_id.name}<br/>
            <strong>Fecha:</strong> {self.invoice_date}<br/>
            <strong>Estado SAT:</strong> Cancelado<br/>
            <br/>
            <em>Por favor, revisar y tomar las acciones correspondientes.</em>
        </div>
        """
        return message

    @api.model
    def _fetch_and_update_sat_status(self, batch_size=None, extra_domain=None):
        """Override para usar parámetros configurables en res.config.settings."""
        ir_config = self.env["ir.config_parameter"].sudo()
        sat_cancellations_channel = self.env.ref("marin.sat_status_cancellation_channel")
        batch_size = batch_size or int(ir_config.get_param("l10n_mx_edi_marin.sat_batch_size", default=100))
        max_days = int(ir_config.get_param("l10n_mx_edi_marin.sat_status_max_days", default=60))
        extra_domain = extra_domain or []
        start_date = datetime.today() - timedelta(days=max_days)
        extra_domain.append(("create_date", ">=", start_date.strftime("%Y-%m-%d")))
        domain = self._get_update_sat_status_domain(extra_domain=extra_domain)
        documents = self.search(domain, limit=batch_size + 1)

        for counter, document in enumerate(documents):
            if counter == batch_size:
                self.env.ref("l10n_mx_edi.ir_cron_update_pac_status_invoice")._trigger()
            else:
                last_sat_state = document.l10n_mx_edi_cfdi_sat_state
                document._update_sat_state()
                if last_sat_state == "valid" and document.l10n_mx_edi_cfdi_sat_state == "cancelled":
                    # Create notification message
                    message = document._get_sat_status_cancellation_message()
                    # Post message to the channel
                    sat_cancellations_channel.message_post(
                        body=message,
                        message_type='notification',
                        subtype_xmlid='mail.mt_comment'
                    )
