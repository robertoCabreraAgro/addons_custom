from odoo import models, api, tools, _
from odoo.osv import expression
from datetime import datetime, timedelta
from zeep import Client, Transport
import logging

_logger = logging.getLogger(__name__)


class L10nMxEdiDocument(models.Model):
    _inherit = "l10n_mx_edi.document"

    def _fetch_sat_status(self, supplier_rfc, customer_rfc, total, uuid):

        url = "https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc?wsdl"
        params = (
            f'?id={uuid or ""}'
            f'&re={tools.html_escape(supplier_rfc or "")}'
            f'&rr={tools.html_escape(customer_rfc or "")}'
            f"&tt={total or 0.0}"
        )
        transport = Transport(timeout=20)

        try:
            client = Client(wsdl=url, transport=transport)
            response = client.service.Consulta(params)
            _logger.info(
                "Fetched SAT status for UUID %s: %s", uuid, response
            )
            fetched_state = response["Estado"] if hasattr(response, "Estado") else ""
            cancel_state = (
                response["EstadoCancelacion"]
                if hasattr(response, "EstadoCancelacion")
                else ""
            )
        except Exception as e:
            return {
                "error": _("Failure during update of the SAT status: %s", str(e)),
                "value": "error",
            }

        if fetched_state == "Cancelado":
            return {"value": "cancelled"}
        elif fetched_state == "Vigente" and cancel_state in (None, "", "None"):
            return {"value": "valid"}
        elif fetched_state == "Vigente" and cancel_state in (
            "En proceso",
            "Plazo vencido",
        ):
            return {"value": "cancelled"}
        elif fetched_state == "No Encontrado":
            return {"value": "not_found"}
        else:
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

    @api.model
    def _fetch_and_update_sat_status(self, batch_size=None, extra_domain=None):
        """Override para usar parámetros configurables en res.config.settings."""
        ir_config = self.env["ir.config_parameter"].sudo()

        # Obtener valores desde configuración
        batch_size = batch_size or int(
            ir_config.get_param("l10n_mx_edi_marin.sat_batch_size", default=100)
        )
        dias_aviles = int(
            ir_config.get_param("l10n_mx_edi_marin.sat_dias_aviles", default=60)
        )

        # Construir dominio extendido
        extra_domain = extra_domain or []
        fecha_limite = datetime.today() - timedelta(days=dias_aviles)
        extra_domain.append(("create_date", ">=", fecha_limite.strftime("%Y-%m-%d")))

        # Buscar documentos según dominio final
        domain = self._get_update_sat_status_domain(extra_domain=extra_domain)

        documents = self.search(domain, limit=batch_size + 1)

        # Procesar documentos, reagendar cron si hay más
        for counter, document in enumerate(documents):
            if counter == batch_size:
                self.env.ref("l10n_mx_edi.ir_cron_update_pac_status_invoice")._trigger()
            else:
                document._update_sat_state()
