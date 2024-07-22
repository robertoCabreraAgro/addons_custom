# import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import split_every

# _logger = logging.getLogger(__name__)


CFDI_TYPE = [
    ("I", "Ingreso"),
    ("E", "Egreso"),
    ("T", "Traslado"),
    ("N", "Nómina"),
    ("P", "Pago"),
    #    ("R", "Retención"),
]
ERROR_TYPE = [
    (0, "Token invalido."),
    (1, "Aceptada"),
    (2, "En proceso"),
    (3, "Terminada"),
    (4, "Error"),
    (5, "Rechazada"),
    (6, "Vencida"),
]
CFDI_COMPLEMENT = []


class SatSyncWizard(models.TransientModel):
    _name = "sat.sync.wizard"
    _description = "SAT sync wizard"

    company_id = fields.Many2one("res.company", "Company", default=lambda self: self.env.company)
    complement = fields.Selection(
        [
            ("acreditamientoieps10", "acreditamientoieps10"),
            ("aerolíneas", "aerolíneas"),
            ("cartaporte10", "cartaporte10"),
            ("cartaporte20", "cartaporte20"),
            ("certificadodedestruccion", "certificadodedestruccion"),
            ("cfdiregistrofiscal", "cfdiregistrofiscal"),
            ("comercioexterior10", "comercioexterior10"),
            ("comercioexterior11", "comercioexterior11"),
            ("comprobante", "comprobante"),
            ("consumodecombustibles", "consumodecombustibles"),
            ("consumodecombustibles11", "consumodecombustibles11"),
            ("detallista", "detallista"),
            ("divisas", "divisas"),
            ("donat11", "donat11"),
            ("ecc11", "ecc11"),
            ("ecc12", "ecc12"),
            ("gastoshidrocarburos10", "gastoshidrocarburos10"),
            ("iedu", "iedu"),
            ("implocal", "implocal"),
            ("ine11", "ine11"),
            ("ingresoshidrocarburos", "ingresoshidrocarburos"),
            ("leyendasfisc", "leyendasfisc"),
            ("nomina11", "nomina11"),
            ("nomina12", "nomina12"),
            ("notariospublicos", "notariospublicos"),
            ("obrasarteantiguedades", "obrasarteantiguedades"),
            ("pagoenespecie", "pagoenespecie"),
            ("pagos10", "pagos10"),
            ("pagos20", "pagos20"),
            ("pfic", "pfic"),
            ("renovacionysustitucionvehiculos", "renovacionysustitucionvehiculos"),
            ("servicioparcialconstruccion", "servicioparcialconstruccion"),
            ("spei", "spei"),
            ("terceros11", "terceros11"),
            ("turistapasajeroextranjero", "turistapasajeroextranjero"),
            ("valesdedespensa", "valesdedespensa"),
            ("vehiculousado", "vehiculousado"),
            ("ventavehiculos11", "ventavehiculos11"),
            ("arrendamientoenfideicomiso", "arrendamientoenfideicomiso"),
            ("dividendos", "dividendos"),
            ("enajenaciondeacciones", "enajenaciondeacciones"),
            ("fideicomisonoempresarial", "fideicomisonoempresarial"),
            ("intereses", "intereses"),
            ("intereseshipotecarios", "intereseshipotecarios"),
            ("operacionesconderivados", "operacionesconderivados"),
            ("pagosaextranjeros", "pagosaextranjeros"),
            ("planesderetiro", "planesderetiro"),
            ("planesderetiro11", "planesderetiro11"),
            ("premios", "premios"),
            ("retencionpago1", "retencionpago1"),
            ("sectorfinanciero", "sectorfinanciero"),
            ("serviciosplataformastecnologicas10", "serviciosplataformastecnologicas10"),
        ],
    )
    cdfi_state = fields.Selection([("0", "Cancelled"), ("1", "Valid")], "State")
    date_from = fields.Datetime(
        "From",
        required=True,
        default=lambda self: self._default_date_from(),
        help="Day 1 of current month by default.",
    )
    date_to = fields.Datetime("To", required=True, default=fields.Datetime.now, help="Today.")
    uuid = fields.Char("UUID")
    thirth_party_vat = fields.Char("Thirth Party VAT")
    emitter_vat = fields.Char("Emitter VAT")
    receiver_vat = fields.Char("Receiver VAT")
    cfdi_type = fields.Selection(CFDI_TYPE, "CFDI Type")
    request_type = fields.Selection([("CFDI", "CFDI"), ("Metadata", "Metadata")], default="CFDI")

    @api.model
    def _default_date_from(self):
        """Day 1 of current month by default."""
        date_from = fields.Datetime.now()
        return date_from.replace(day=1)

    @api.onchange("date_from", "date_to")
    def _onchange_date(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise UserError(_('"Date to" must be greater than "Date from"'))

    @api.onchange("uuid")
    def _onchange_uuid(self):
        if self.uuid:
            self.complement = False
            # self.cfdi_state = False
            self.date_from = False
            self.date_to = False
            self.thirth_party_vat = False
            self.emitter_vat = False
            self.receiver_vat = False
            self.cfdi_type = False

    def get_params(self):
        params = {"date_to": self.date_to, "date_from": self.date_from}
        if self.complement:
            params.update({"complement": self.complement})
        if self.uuid:
            params.update({"uuid": self.uuid})
        if self.date_from:
            params.update({"date_from": self.date_from})
        if self.date_to:
            params.update({"date_to": self.date_to})
        if self.thirth_party_vat:
            params.update({"thirth_party_vat": self.thirth_party_vat})
        if self.emitter_vat:
            params.update({"emitter_vat": self.emitter_vat})
        if self.receiver_vat:
            params.update({"receiver_vat": self.receiver_vat})
        if self.cfdi_type:
            params.update({"cfdi_type": self.cfdi_type})
        if self.request_type:
            params.update({"request_type": self.request_type})
        return params

    def download_cfdi_files(self):
        attachment_ids = []
        for company in self.company_id:
            params = self.get_params()
            attachment_ids.extend(company.download_cfdi_files(**params))
        action = self.env.ref("base.action_attachment").read()[0]
        action["domain"] = [("id", "in", attachment_ids)]
        return action

    def action_button_reprocess(self):
        process_move_ids = []
        moves = self.get_moves()
        if not moves:
            raise UserError(_("No records found for your selection."))
        move_obj = self.env["account.move"]
        for record in split_every(100, moves.ids):
            for move in move_obj.browse(record):
                res = self.action_fix_move_cash_basis(move)
                if res:
                    process_move_ids.append(move.id)
        # _logger.debug("%d account moves reprocesed.", len(process_move_ids))
        return {
            "type": "ir.actions.act_window",
            "name": _("Reprocess Account Moves"),
            "res_model": "account.move",
            "domain": [("id", "in", process_move_ids)],
            "view_type": "form",
            "view_mode": "tree,form",
            "context": self.env.context,
            "target": "current",
        }
