import logging
import uuid

import requests
from requests.exceptions import ConnectionError as ConnError, RequestException, Timeout

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

ENDPOINT_URL = {
    "prod": "https://conagrosyngentapp.syngentadigitalapps.com/syngenta-service-0.0.1/api/v1/Sellout",
    "test": "https://conagrosyngentapp.syngentadigitalapps.com/syngenta-service-0.0.1/api/v1/test/Sellout",
}


class SyngentaSaleReport(models.Model):
    _name = "syngenta.sale.report"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"
    _description = "Report send to Syngenta with customer's consumptions"

    name = fields.Char(
        string="Document Reference",
        required=True,
        copy=False,
        readonly=False,
        index="trigram",
        default=lambda self: _("New"),
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("sent", "Sent"),
            ("done", "Done"),
            ("cancel", "Cancel"),
            ("error", "Error"),
        ],
        default="draft",
        readonly=True,
        required=True,
    )
    date = fields.Date(required=True, default=fields.Date.end_of(fields.Date.today(), "month"))
    agreement_id = fields.Many2one(
        "syngenta.commercial.agreement",
        "Agreement",
        required=True,
    )
    sale_line_ids = fields.One2many(
        "syngenta.sale.report.line",
        "document_id",
        "Sale Lines",
        domain="[('agreement_id', '=', agreement_id)]",
    )
    folio = fields.Char(compute="_compute_folio", store=True)
    partner_id = fields.Many2one(related="agreement_id.partner_id", readonly=True)
    response_message = fields.Text(readonly=True, copy=False)
    response_status = fields.Char(readonly=True, copy=False)
    response_error = fields.Char(readonly=True, copy=False)
    response_json = fields.Text(readonly=True, copy=False)
    sent_json = fields.Text(readonly=True, copy=False)
    company_id = fields.Many2one("res.company", index=True, required=True, default=lambda self: self.env.company.id)

    def _compute_folio(self):
        for rec in self.filtered(lambda doc: not doc.folio):
            folio = self._get_random_folio()
            doc = self.search([("folio", "=", folio)], limit=1)
            while doc:
                folio = self._get_random_folio()
                doc = self.search([("folio", "=", folio)], limit=1)
            rec.folio = folio

    def _get_random_folio(self, limit=13):
        return str(uuid.uuid4())[:limit]

    def _get_json_data(self):
        lines = self.sale_line_ids._get_json_lines()
        return {
            "clave_Distribuidor": self.company_id.syngenta_customer_code,
            "nombre_distribuidor": self.company_id.name,
            "productLines": lines,
        }

    def _get_url(self):
        env = "test" if self.company_id.syngenta_demo else "prod"
        return ENDPOINT_URL[env]

    def action_send(self):
        if self.state in ["done", "cancel"]:
            return
        if not self.folio:
            self._compute_folio()
        timeout = int(self.env["ir.config_parameter"].sudo().get_param("syngenta_edi.request_timeout")) or 60
        data = self._get_json_data()
        endpoint_url = self._get_url()
        try:
            resp = requests.post(url=endpoint_url, json=data, timeout=timeout)
            resp_json = resp.json()
            return self._handle_response(resp_json, data)
        except (Timeout, ConnError, RequestException, ValueError):
            _logger.warning("Syngenta synchronization error")
            raise UserError(
                _("The syngenta synchronization service is not available at the moment. " "Please try again later.")
            )

    def _handle_response(self, res, data):
        not_error = not res.get("error") or res.get("error") in ["false", "False"]
        self.write(
            {
                "state": "done" if not_error else "error",
                "response_message": res.get("message"),
                "response_status": res.get("status"),
                "response_error": "" if not_error else res.get("error"),
                "response_json": res,
                "sent_json": data,
            }
        )

    def action_cancel(self):
        self.filtered(lambda doc: doc.state not in ["done", "cancel"]).state = "cancel"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "company_id" in vals:
                self = self.with_company(vals["company_id"])
            if vals.get("name", _("New")) == _("New"):
                seq_date = (
                    fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(vals["date"]))
                    if "date" in vals
                    else None
                )
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "syngenta.sale.report", sequence_date=seq_date
                ) or _("New")
        return super().create(vals_list)
