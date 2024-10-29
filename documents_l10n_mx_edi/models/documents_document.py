import json
from os.path import splitext

from odoo import _, api, fields, models, Command


STATUS = {
    "No Encontrado": "not_found",
    "Cancelado": "cancelled",
    "Vigente": "valid",
}
CANCELLABLE = {
    "No Cancelable": "not_cancellable",
    "Cancelable sin aceptación": "cancellable_no_auth",
    "Cancelable con aceptación": "cancellable_auth",
}
CANCEL_STATUS = {
    "En proceso": "in_process",
    "Cancelado sin aceptación": "cancelled_no_auth",
    "Cancelado con aceptación": "cancelled_auth",
    "Plazo vencido": "cancelled_timeout",
    "Solicitud rechazada": "rejected",
}


class Document(models.Model):
    _inherit = "documents.document"


    l10n_mx_edi_is_cfdi = fields.Boolean(help="Specify if this is a CFDI document.")
    l10n_mx_edi_sat_state = fields.Selection(
        [
            ("none", "State not defined"),
            ("not_found", "Not Found"),
            ("cancelled", "Cancelled"),
            ("valid", "Valid")
        ],
        "SAT Status",
        default="none",
        tracking=True,
        readonly=True,
        copy=False,
        help="Refers to the status of the invoice inside the SAT system.",
    )
    l10n_mx_edi_sat_cancellable = fields.Selection(
        [
            ("none", "State not defined"),
            ("not_cancellable", "Not Cancellable"),
            ("cancellable_auth", "Cancellable with authorization"),
            ("cancellable_no_auth", "Cancellable without authorization"),
        ],
        string="Cancellable",
        default="none",
        tracking=True,
        readonly=True,
        copy=False,
        help="Indicate wheter the document can be cancelled or not.",
    )
    l10n_mx_edi_sat_cancel_state = fields.Selection(
        [
            ("none", "State not defined"),
            ("in_process", "In Process"),
            ("cancelled_no_auth", "Cancelled without authorization"),
            ("cancelled_auth", "Cancelled with authorization"),
            ("cancelled_timeout", "Cancelled because timeout"),
            ("rejected", "Cancellation Rejected"),
        ],
        "Cancellation Status",
        default="none",
        tracking=True,
        readonly=True,
        copy=False,
        help="Refers to the status of the cancellation in the SAT system.",
    )
    l10n_mx_edi_stamp_date = fields.Datetime(
        "CFDI stamp date", compute="_compute_l10n_mx_edi_common_fields", store=True
    )
    l10n_mx_edi_cfdi_total_amount = fields.Float(
        "Total Amount",
        compute="_compute_l10n_mx_edi_common_fields", store=True,
        help='In case this is a CFDI file, stores invoice"s total amount.',
    )
    l10n_mx_edi_related_cfdi = fields.Text(
        "Related CFDI",
        compute="_compute_l10n_mx_edi_common_fields", store=True,
        help="Related CFDI of the XML file"
    )
    l10n_mx_edi_product_list = fields.Text(
        "Products",
        compute="_compute_l10n_mx_edi_common_fields",
        store=True,
        help='In case this is a CFDI file, show invoice"s product list',
    )


    def check_document_already_linked(self):
        if documents_link_record := self.filtered(
            lambda d: d.res_model != 'documents.document'
        ):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': _(
                        "Already linked Documents: %s",
                        ", ".join(documents_link_record.mapped('name'))
                    ),
                }
            }

    def prepare_action_create_from_cfdi(self):
        action = {
            'name': _('MX EDI to record'),
            'type': 'ir.actions.act_window',
            'res_model': 'documents.mx_edi_to_record_wizard',
            'view_mode': 'form',
            'target': 'new',
            'views': [(False, "form")],
            "context": {}
        }
        return action

    def create_from_cfdi(self):
        check = self.check_document_already_linked()
        if check:
            return check
        action = self.prepare_action_create_from_cfdi()
        action.update({"context": {"default_document_ids": self.ids}})
        return action

    def prepare_l10n_mx_edi_common_fields(self, document):
        vals = {}
        edi_obj = self.env["l10n_mx_edi.document"]
        cfdi_etree = edi_obj.check_objectify_xml(document.datas)
        partner = edi_obj.partner_search_create(cfdi_etree)
        tfd_node = edi_obj.collect_complemento(cfdi_etree)
        product_list = []
        for line in cfdi_etree.Conceptos.Concepto:
            product_list += [line.get("Descripcion", "")]
        vals.update(
            {
                "partner_id": partner.id,
                "l10n_mx_edi_cfdi_total_amount": float(cfdi_etree.get("Total", 0)),
                "l10n_mx_edi_stamp_date": edi_obj.get_datetime(tfd_node),
                "l10n_mx_edi_product_list": json.dumps(product_list),
            }
        )
        # if hasattr(cfdi_etree, "CfdiRelacionados"):
        #     related_uuids = edi_obj.get_related_uuids_dict(cfdi_etree)
        #     l10n_mx_edi_origin = self.env["account.move"]._l10n_mx_edi_write_cfdi_origin(
        #         related_uuids["type"], related_uuids["uuids"]
        #     )
        #     vals.update({"l10n_mx_edi_related_cfdi": json.dumps(l10n_mx_edi_origin)})
        return vals

    @api.depends("datas")
    def _compute_l10n_mx_edi_common_fields(self):
        for rec in self.filtered(lambda doc: doc.l10n_mx_edi_is_cfdi and doc.attachment_id):
            vals = self.prepare_l10n_mx_edi_common_fields(rec)
            rec.update(vals)

    def update_l10n_mx_edi_sat_state(self):
        for rec in self:
            if not rec.l10n_mx_edi_is_cfdi or not rec.datas:
                rec.l10n_mx_edi_sat_state = "none"
                rec.l10n_mx_edi_sat_cancellable = "none"
                rec.l10n_mx_edi_sat_cancel_state = "none"
                continue

            cfdi_etree = self.env["l10n_mx_edi.document"].check_objectify_xml(rec.datas)
            uuid = self.env["l10n_mx_edi.document"].collect_complemento(cfdi_etree).get("UUID", "").upper()
            sat_status = self.env["l10n_mx_edi.document"].l10n_mx_ws_get_cfdi_status(
                cfdi_etree.Emisor.get("Rfc", ""),
                cfdi_etree.Receptor.get("Rfc", ""),
                cfdi_etree.get("Total", "0.00"),
                uuid,
            )
            rec.l10n_mx_edi_sat_state = STATUS.get(sat_status["status"] if sat_status else "none", "none")
            rec.l10n_mx_edi_sat_cancellable = CANCELLABLE.get(
                sat_status["is_cancellable"] if sat_status else "", "none"
            )
            rec.l10n_mx_edi_sat_cancel_state = CANCEL_STATUS.get(
                sat_status["cancel_status"] if sat_status else "", "none"
            )

    def _get_l10n_mx_edi_type_tag(self, key):
        values = {
            "I": self.env.ref("documents_l10n_mx_edi.documents_l10n_mx_edi_tag_ingreso"),
            "E": self.env.ref("documents_l10n_mx_edi.documents_l10n_mx_edi_tag_egreso"),
            "T": self.env.ref("documents_l10n_mx_edi.documents_l10n_mx_edi_tag_traslado"),
            "P": self.env.ref("documents_l10n_mx_edi.documents_l10n_mx_edi_tag_reception"),
            "N": self.env.ref("documents_l10n_mx_edi.documents_l10n_mx_edi_tag_nomina"),
            "R": self.env.ref("documents_l10n_mx_edi.documents_l10n_mx_edi_tag_retencion"),
        }
        return values.get(key, ())

    def _prepare_l10n_mx_edi_tags(self, cfdi_etree):
        tag_obj = self.env["documents.tag"]
        tags = []
        tag = self._get_l10n_mx_edi_type_tag(cfdi_etree.get("TipoDeComprobante"))
        if tag:
            tags.append(tag.id)
        tag = tag_obj.search(
            [
                ("name", "=", str(self.env["l10n_mx_edi.document"].get_datetime(cfdi_etree).year)),
            ],
            limit=1,
        )
        if tag:
            tags.append(tag.id)
        tag = tag_obj.search(
            [
                ("name", "=", str(self.env["l10n_mx_edi.document"].get_datetime(cfdi_etree).month)),
            ],
            limit=1,
        )
        if tag:
            tags.append(tag.id)
        return tags

    def _documents_l10n_mx_edi_get_folder(self, cfdi_etree):
        import_type = "issued" if self.env.company.vat == cfdi_etree.Emisor.get("Rfc", "") else "received"
        folder = (
            self.env.ref("documents_l10n_mx_edi.documents_l10n_mx_edi_folder_issued")
            if import_type == "issued"
            else self.env.ref("documents_l10n_mx_edi.documents_l10n_mx_edi_folder_received")
        )
        return folder

    def _l10n_edi_document_assign_tags_and_folder(self):
        etree = self.env["l10n_mx_edi.document"].check_objectify_xml(self.datas)
        tags = [
            "{http://www.sat.gob.mx/cfd/3}Comprobante",
            "{http://www.sat.gob.mx/cfd/4}Comprobante",
        ]
        is_cfdi = etree.tag in tags
        if is_cfdi:
            uuid = self.env["l10n_mx_edi.document"].collect_complemento(etree).get("UUID", "").upper()
            exist_docs = self.env["documents.document"].search(
                [
                    ("id", "!=", self.id),
                    ("name", "ilike", uuid + ".xml"),
                    ("res_model", "=", "documents.document"),
                ]
            )
            if exist_docs:
                # Add duplicated tag
                message = _("Duplicated CFDI: %s" % uuid)
                self.env["bus.bus"]._sendone(
                    self.env.user.partner_id,
                    "simple_notification",
                    {"title": "Duplicated CFDI", "message": message, "sticky": False, "warning": True},
                )
            else:
                tag_ids = self._prepare_l10n_mx_edi_tags(etree)
                self.update(
                    {
                        "name": uuid + ".xml",
                        "folder_id": self._documents_l10n_mx_edi_get_folder(etree).id,
                        "l10n_mx_edi_is_cfdi": True,
                        "tag_ids": [Command.set(tag_ids)],
                    }
                )

    @api.model_create_multi
    def create(self, vals_list):
        documents = super().create(vals_list)
        for doc in documents.filtered(lambda r: splitext(r.name)[1].upper() == ".XML"):
            doc._l10n_edi_document_assign_tags_and_folder()
        return documents
