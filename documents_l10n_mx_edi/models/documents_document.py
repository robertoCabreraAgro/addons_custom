import json

from odoo import _, api, fields, models

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
        compute="_compute_l10n_mx_edi_common_fields",
        store=True,
        help='In case this is a CFDI file, stores invoice"s total amount.',
    )
    l10n_mx_edi_related_cfdi = fields.Text(
        "Related CFDI", compute="_compute_l10n_mx_edi_common_fields", store=True, help="Related CFDI of the XML file"
    )
    l10n_mx_edi_product_list = fields.Text(
        "Products",
        compute="_compute_l10n_mx_edi_common_fields",
        store=True,
        help='In case this is a CFDI file, show invoice"s product list',
    )

    def check_document_already_linked(self):
        documents_link_record = [d for d in self if d.res_model != "documents.document"]
        if documents_link_record:
            return {
                'warning': {
                    'title': _("Already linked Documents"),
                    'documents': [d.name for d in documents_link_record],
                }
            }

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
        related_uuids = edi_obj.get_related_uuids_dict(cfdi_etree)
        if related_uuids:
            l10n_mx_edi_origin = self.env["account.move"]._l10n_mx_edi_write_cfdi_origin(
                related_uuids["type"], related_uuids["uuids"]
            )
            vals.update({"l10n_mx_edi_related_cfdi": json.dumps(l10n_mx_edi_origin)})
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
                ("facet_id", "=", self.env.ref("documents_l10n_mx_edi.documents_l10n_mx_edi_facet_fiscal_year").id),
                ("name", "=", str(self.env["l10n_mx_edi.document"].get_datetime(cfdi_etree).year)),
            ],
            limit=1,
        )
        if tag:
            tags.append(tag.id)
        tag = tag_obj.search(
            [
                ("facet_id", "=", self.env.ref("documents_l10n_mx_edi.documents_l10n_mx_edi_facet_fiscal_month").id),
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

    def _l10n_mx_edi_validate_create_vals(self, vals_list):
        edi_obj = self.env["l10n_mx_edi.document"]
        container = []
        duplicated_docs = []
        for vals in vals_list:
            if "datas" not in vals:
                container.append(vals)
                continue

            cfdi_etree = edi_obj.check_objectify_xml(vals["datas"])
            tags = [
            "{http://www.sat.gob.mx/cfd/3}Comprobante",
            "{http://www.sat.gob.mx/cfd/4}Comprobante",
            ]
            is_cfdi = cfdi_etree.tag in tags
            if not is_cfdi:
                container.append(vals)
                continue

            uuid = edi_obj.collect_complemento(cfdi_etree).get("UUID", "").upper()
            exist_docs = self.search(
                [
                    ("name", "=", uuid + ".xml"),
                    ("company_id", "=", self.env.company.id),
                ]
            )
            if not exist_docs:
                tag_ids = self._prepare_l10n_mx_edi_tags(cfdi_etree)
                folder = self._documents_l10n_mx_edi_get_folder(cfdi_etree)
                if "tags_ids" in vals:
                    vals["tag_ids"].append(tag_ids)
                else:
                    vals.update({"tag_ids": tag_ids})
                if "l10n_mx_edi_is_cfdi" not in vals:
                    vals.update({"l10n_mx_edi_is_cfdi": True})
                vals.update(
                    {
                        "name": uuid + ".xml",
                        "folder_id": folder.id,
                    }
                )
                container.append(vals)
                continue

            message = _("Duplicated CFDI, document creation skipped.")
            self.env["bus.bus"]._sendone(
                self.env.user.partner_id,
                "simple_notification",
                {"title": "Duplicated CFDI", "message": message, "sticky": False, "warning": True},
            )
            duplicated_docs.append(vals)
            continue

        if duplicated_docs and not container:
            return []

        return container

    @api.model_create_multi
    def create(self, vals_list):
        new_vals_list = self._l10n_mx_edi_validate_create_vals(vals_list)
        return super().create(new_vals_list)
