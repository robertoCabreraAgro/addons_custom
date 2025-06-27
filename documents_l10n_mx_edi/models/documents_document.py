import json
import logging
from datetime import datetime, timedelta
from os.path import splitext

from requests.exceptions import ConnectTimeout, HTTPError, RequestException

from odoo import Command, api, fields, models

_logger = logging.getLogger(__name__)


class Document(models.Model):
    _inherit = "documents.document"

    l10n_mx_edi_is_cfdi = fields.Boolean(help="Specify if this is a CFDI document.")
    l10n_mx_edi_cfdi_sat_state = fields.Selection(
        string="SAT status",
        selection=[
            ("valid", "Validated"),
            ("cancelled", "Cancelled"),
            ("not_found", "Not Found"),
            ("not_defined", "Not Defined"),
            ("error", "Error"),
        ],
        store=True,
        copy=False,
        tracking=True,
    )
    l10n_mx_edi_stamp_date = fields.Datetime(
        string="CFDI stamp date",
        compute="_compute_l10n_mx_edi_common_fields",
        store=True,
    )
    l10n_mx_edi_cfdi_total_amount = fields.Float(
        string="Total Amount",
        compute="_compute_l10n_mx_edi_common_fields",
        store=True,
        help='In case this is a CFDI file, stores invoice"s total amount.',
    )
    l10n_mx_edi_related_cfdi = fields.Text(
        string="Related CFDI",
        compute="_compute_l10n_mx_edi_common_fields",
        store=True,
        help="Related CFDI of the XML file",
    )
    l10n_mx_edi_product_list = fields.Text(
        string="Products",
        compute="_compute_l10n_mx_edi_common_fields",
        store=True,
        help='In case this is a CFDI file, show invoice"s product list',
    )
    l10n_mx_edi_is_cfdi_payment = fields.Boolean(
        string="Is a Payment Complement",
        compute="_compute_l10n_mx_edi_common_fields",
        store=True,
        help="Specify if this is a CFDI Payment document.",
    )
    vendor_bill_name = fields.Char(
        string="Vendor Bill",
        compute="_compute_vendor_bill_name",
    )
    last_sat_state_sync_date = fields.Datetime(
        string="Last SAT Status Sync", readonly=True, default=fields.Datetime.now
    )

    @api.depends("res_model", "res_id")
    def _compute_vendor_bill_name(self):
        account_move = self.env["account.move"]
        for document in self:
            vendor_bill_name = ""
            if (
                document.res_model == "account.move"
                and document.res_id
                and account_move.browse(document.res_id).is_purchase_document()
            ):
                vendor_bill_name = account_move.browse(document.res_id).name
            document.vendor_bill_name = vendor_bill_name

    def check_document_already_linked(self):
        if documents_link_record := self.filtered(lambda d: d.res_model != "documents.document"):
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "type": "warning",
                    "message": self.env._(
                        "Already linked Documents: %s",
                        ", ".join(documents_link_record.mapped("name")),
                    ),
                },
            }

    def create_from_cfdi(self):
        check = self.check_document_already_linked()
        if check:
            return check
        return {
            "name": self.env._("MX EDI to record"),
            "type": "ir.actions.act_window",
            "res_model": "documents.mx_edi_to_record_wizard",
            "view_mode": "form",
            "target": "new",
            "views": [(False, "form")],
            "context": {"default_document_ids": self.ids},
        }

    def _prepare_l10n_mx_edi_common_fields(self, document):
        vals = {}
        mx_edi_document = self.env["l10n_mx_edi.document"]
        cfdi_infos = mx_edi_document._decode_cfdi_attachment(document.raw)
        cfdi_node = cfdi_infos["cfdi_node"]
        partner = mx_edi_document.partner_search_create(cfdi_node)
        is_cfdi_payment = mx_edi_document._l10n_mx_edi_is_cfdi_payment(cfdi_node)
        product_list = []
        for line in cfdi_node.findall("{*}Conceptos/{*}Concepto")[0]:
            product_list += [line.get("Descripcion", "")]
        vals.update(
            {
                "partner_id": partner.id,
                "l10n_mx_edi_cfdi_total_amount": float(cfdi_infos["amount_total"]),
                "l10n_mx_edi_stamp_date": cfdi_infos["stamp_date"],
                "l10n_mx_edi_product_list": json.dumps(product_list),
                "l10n_mx_edi_is_cfdi_payment": is_cfdi_payment,
                "l10n_mx_edi_related_cfdi": cfdi_infos["origin"],
            }
        )
        return vals

    @api.depends("datas")
    def _compute_l10n_mx_edi_common_fields(self):
        for rec in self.filtered(lambda doc: doc.l10n_mx_edi_is_cfdi and doc.attachment_id):
            vals = self._prepare_l10n_mx_edi_common_fields(rec)
            rec.update(vals)

    @api.model
    def _get_update_sat_status_domain(self, start_date=None):
        domain = [
            ("l10n_mx_edi_is_cfdi", "=", True),
            ("res_model", "=", "documents.document"),
        ]
        if start_date:
            domain.append(("l10n_mx_edi_stamp_date", ">=", start_date.strftime("%Y-%m-%d")))

        return domain

    @api.model
    def _cron_update_sat_status(self):
        """Update SAT status of fiscal documents that:
        1. Are stamped
        2. Don't have a related account move
        3. Are as recent as 60 days.
        """
        ir_config = self.env["ir.config_parameter"].sudo()
        batch_size = int(ir_config.get_param("l10n_mx_edi_marin.sat_batch_size", default=100))
        max_days = int(ir_config.get_param("l10n_mx_edi_marin.sat_status_max_days", default=60))
        start_date = datetime.now() - timedelta(days=max_days)
        domain = self._get_update_sat_status_domain(start_date=start_date)

        documents = self.search(domain, limit=batch_size + 1, order="last_sat_state_sync_date, id")
        sync_date = fields.Datetime.now()
        auto_commit = self.env.context.get("auto_commit", True)
        processed_documents = self.browse()

        for document in documents:
            try:
                document._update_sat_state()
                if auto_commit:
                    self.env.cr.commit()  # pylint: disable=invalid-commit

            except (ConnectTimeout, HTTPError, RequestException):
                # Network/SAT service errors - propagate to trigger retry mechanism
                _logger.info(
                    "Network error occurred while updating SAT status for document %s. "
                    "Operation will be retried later.",
                    document.name,
                )
                raise

            except Exception:
                # Business errors - log and continue with next document
                _logger.warning(
                    "Business error occurred while updating SAT status for document %s. "
                    "Skipping document and moving to next one.",
                    document.name,
                    exc_info=True,
                )
                self.env.cr.rollback()
                continue

            processed_documents |= document

        processed_documents.write({"last_sat_state_sync_date": sync_date})

    def _update_sat_state(self):
        self.ensure_one()
        mx_edi_document = self.env["l10n_mx_edi.document"]
        if not self.l10n_mx_edi_is_cfdi or not self.raw:
            self.l10n_mx_edi_cfdi_sat_state = None
            return

        cfdi_infos = mx_edi_document._decode_cfdi_attachment(self.raw)
        if not cfdi_infos:
            self.l10n_mx_edi_cfdi_sat_state = None
            return

        sat_results = mx_edi_document._fetch_sat_status(
            cfdi_infos["supplier_rfc"],
            cfdi_infos["customer_rfc"],
            cfdi_infos["amount_total"],
            cfdi_infos["uuid"],
        )

        sat_state = sat_results.get("value")
        sat_error = sat_results.get("error")
        if sat_state == "error" and sat_error:
            self.message_post(body=sat_error)

        self.l10n_mx_edi_cfdi_sat_state = sat_state

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

    def _prepare_l10n_mx_edi_tags(self, cfdi_infos):
        cfdi_node = cfdi_infos["cfdi_node"]
        stamp_date = datetime.strptime(cfdi_infos["stamp_date"], "%Y-%m-%d %H:%M:%S")
        tag_obj = self.env["documents.tag"]
        tags = []
        tag = self._get_l10n_mx_edi_type_tag(cfdi_node.get("TipoDeComprobante"))
        if tag:
            tags.append(tag.id)
        tag = tag_obj.search(
            [
                (
                    "name",
                    "=",
                    str(stamp_date.year),
                ),
            ],
            limit=1,
            order="id desc",
        )
        if tag:
            tags.append(tag.id)
        tag = tag_obj.search(
            [
                (
                    "name",
                    "=",
                    str(stamp_date.month),
                ),
            ],
            limit=1,
        )
        if tag:
            tags.append(tag.id)
        return tags

    def _documents_l10n_mx_edi_get_folder(self, rfc_emisor):
        import_type = "issued" if self.env.company.vat == rfc_emisor else "received"
        folder = (
            self.env.ref("documents_l10n_mx_edi.documents_l10n_mx_edi_folder_issued")
            if import_type == "issued"
            else self.env.ref("documents_l10n_mx_edi.documents_l10n_mx_edi_folder_received")
        )
        return folder

    def _documents_l10n_mx_edi_get_company(self, rfc):
        """Finds a company by RFC (with or without MX prefix).

        Args:
            rfc (str): RFC to search for

        Returns:
            recordset: The found company or False
        """
        if not rfc:
            return False
        return self.env["res.company"].search(["|", ("vat", "=", rfc), ("vat", "=", "MX" + rfc)], limit=1)

    def _l10n_mx_edi_assign_cfdi_data(self):
        """Assign tags, folder and company to the document based on CFDI content.

        This method will:
        - Verify if the document is a valid CFDI
        - Check for duplicates by UUID
        - Assign appropriate tags and folder
        - Link the document to the corresponding company
        """
        mx_edi_document = self.env["l10n_mx_edi.document"]
        cfdi_infos = mx_edi_document._decode_cfdi_attachment(self.raw)
        if not cfdi_infos or not cfdi_infos.get("uuid"):
            return False

        # Company assignment
        company = self._documents_l10n_mx_edi_get_company(
            cfdi_infos["customer_rfc"]
        ) or self._documents_l10n_mx_edi_get_company(cfdi_infos["supplier_rfc"])

        # Prepare values to update
        update_vals = {
            "name": mx_edi_document._l10n_mx_edi_normalize_cfdi_filename(cfdi_infos["uuid"]),
            "folder_id": self._documents_l10n_mx_edi_get_folder(cfdi_infos["supplier_rfc"]).id,
            "l10n_mx_edi_is_cfdi": True,
            "tag_ids": [Command.link(tag_id) for tag_id in self._prepare_l10n_mx_edi_tags(cfdi_infos)],
        }

        if company and not self.company_id:
            update_vals["company_id"] = company.id

        self.write(update_vals)

    @api.model_create_multi
    def create(self, vals_list):
        mx_edi_document = self.env["l10n_mx_edi.document"]
        check_duplicate = self.env.context.get("check_duplicate", True)
        existing_documents = self
        new_vals_list = []
        for vals in vals_list:
            name = vals.get("name")
            attachment_id = vals.get("attachment_id")
            if not name and attachment_id:
                name = self.env["ir.attachment"].browse(attachment_id).name
            if name and name.lower().endswith(".xml") and check_duplicate:
                duplicity_result = mx_edi_document._get_duplicate_cfdi(name, self)
                if duplicity_result["duplicated"]:
                    existing_documents |= duplicity_result["document"]
                    self.env["bus.bus"]._sendone(
                        self.env.user.partner_id,
                        "simple_notification",
                        {
                            "title": "Duplicated CFDI",
                            "message": duplicity_result["message"],
                            "sticky": False,
                            "warning": True,
                        },
                    )
                    continue

            new_vals_list.append(vals)

        created_documents = super().create(new_vals_list)
        for doc in created_documents.filtered(lambda r: splitext(r.name)[1].upper() == ".XML"):
            doc._l10n_mx_edi_assign_cfdi_data()
        return created_documents | existing_documents
