import base64
import hashlib
import logging
import os
import re
from datetime import datetime, timedelta

import requests
from lxml import etree
from OpenSSL import crypto

from odoo import models, tools
from odoo.exceptions import ValidationError
from odoo.fields import Command
from odoo.osv import expression
from odoo.tools.float_utils import float_round

TYPE_CFDI22_TO_CFDI33 = {
    "ingreso": "I",
    "egreso": "E",
    "traslado": "T",
    "nomina": "N",
    "pago": "P",
}
MXWS_ERROR_TYPE = [
    ("0", "Token invalido."),
    ("1", "Aceptada"),
    ("2", "En proceso"),
    ("3", "Terminada"),
    ("4", "Error"),
    ("5", "Rechazada"),
    ("6", "Vencida"),
]


_logger = logging.getLogger(__name__)


class L10nMxEdiDocument(models.Model):
    _inherit = "l10n_mx_edi.document"

    def _l10n_mx_edi_is_cfdi(self, cfdi_data):
        cfdi_infos = self.env["l10n_mx_edi.document"]._decode_cfdi_attachment(cfdi_data)
        return bool(cfdi_infos)

    def _l10n_mx_edi_is_cfdi_payment(self, cfdi_node):
        return cfdi_node.get("TipoDeComprobante", False) == "P"

    def _l10n_mx_edi_normalize_cfdi_filename(self, filename):
        """Normalize a filename for CFDI documents.

        This method ensures consistent filename formatting across the module:
        - Removes any existing extension
        - Converts to uppercase
        - Adds .xml extension

        Args:
            filename (str): Original filename or UUID

        Returns:
            str: Normalized filename in format "NAME.xml"

        Examples:
            >>> self._normalize_cfdi_filename("a3abbd51-8189-4a3e-8d0a-71712ebf1479")
            "A3ABBD51-8189-4A3E-8D0A-71712EBF1479.xml"
            >>> self._normalize_cfdi_filename("invoice.xml")
            "INVOICE.xml"
            >>> self._normalize_cfdi_filename("a3abbd51.PDF")
            "A3ABBD51.xml"
        """
        if not filename:
            return ""

        # Strip any existing extension
        base_name = os.path.splitext(filename)[0]

        # Convert to uppercase and add .XML extension
        return base_name.upper() + ".xml"

    def _get_duplicate_cfdi_domain(self, filenames, company_id=None):
        """Build domain to search for duplicate CFDI documents by filename.

        Args:
            filenames (list): List of normalized filenames to search for
            company_id (int, optional): Company ID to restrict search to

        Returns:
            list: Domain expression for document search
        """
        if not company_id:
            company_id = self.env.company.id

        return expression.AND(
            [
                [("company_id", "in", [False, company_id])],
                expression.OR(
                    [[("name", "=ilike", self._l10n_mx_edi_normalize_cfdi_filename(fname))] for fname in filenames]
                ),
            ]
        )

    def _get_duplicate_cfdi(self, uuid, record):
        """Unified method to check UUID duplicity across documents and invoices.

        This method centralizes the logic to detect if a UUID already exists in the system,
        avoiding duplications in both documents module and account_move.

        Args:
            uuid (str): UUID of the CFDI to check for duplicity
            record (Model): Record to exclude from duplicity check.
                           Must be a documents.document or account.move record.

        Returns:
            dict: A dictionary with the following structure:
                {
                    'duplicated': (bool) True if UUID is duplicated, False otherwise,
                    'document_id': (int or False) ID of the duplicate document if exists,
                    'move_id': (int or False) ID of the duplicate invoice if exists,
                    'message': (str) Message describing the duplicity if exists
                }

        Raises:
            ValueError: If record is not a valid record or not of the expected model types
        """
        # Default result
        result = {
            "duplicated": False,
            "document": self.env["documents.document"],
            "move": self.env["account.move"],
            "message": "",
        }

        if not uuid:
            return result

        # Validate parameter
        if not isinstance(record, models.BaseModel) or not record.id:
            raise ValueError(
                "You must provide an existing database record, please save before checking for duplicates"
            )

        if record._name not in ["documents.document", "account.move"]:
            raise ValueError("Duplicates can only be checked for documents or invoices, please provide a valid record")

        # Common message prefix
        message_prefix = self.env._("Duplicated CFDI: %s", uuid)

        if record._name == "documents.document":
            domain = self._get_duplicate_cfdi_domain([uuid], company_id=record.compnay_id.id)
            domain = expression.AND([[("id", "!=", record.id)], domain])

            # Check if UUID exists in documents, excluding current record
            existing_document = self.env["documents.document"].search(domain, limit=1)
            if existing_document:
                result.update(
                    {
                        "duplicated": True,
                        "document": existing_document,
                        "message": f"{message_prefix}\n{self.env._('Already exists as document: %s', existing_document.name)}",
                    }
                )
                return result

        # Check in account.move (for both document and move)
        existing_move = self.env["account.move"].search(
            [
                ("l10n_mx_edi_cfdi_uuid", "=", uuid),
                ("state", "in", ["draft", "posted"]),
                ("id", "!=", record.id),
            ],
            limit=1,
        )

        if existing_move:
            result.update(
                {
                    "duplicated": True,
                    "move": existing_move,
                    "message": f"{message_prefix}\n{self.env._('Already exists as invoice: %s', existing_move.name)}",
                }
            )
            return result

        return result

    def _get_import_type(self, rfc_emisor):
        return "issued" if self.env.company.vat == rfc_emisor else "received"

    def _get_move_type(self, cfdi_infos):
        """Determine invoice type based on CFDI.

        Args:
            cfdi_infos (dict): Must contain:
                - 'cfdi_node' (etree): XML node
                - 'supplier_rfc' (str)

        Returns:
            str: One of 'in_invoice', 'out_refund', etc.

        Example:
            >>> _get_move_type({'supplier_rfc': 'XAXX010101000', ...})
            'out_invoice'
        """
        cfdi_node = cfdi_infos["cfdi_node"]
        cfdi_type = cfdi_node.get("TipoDeComprobante", False)
        move_type = None
        import_type = self._get_import_type(cfdi_infos["supplier_rfc"])
        if import_type == "received":
            received_move_type = {
                "I": "in_invoice",
                "E": "in_refund",
                "N": "entry",
                "P": "entry",
            }
            move_type = received_move_type.get(cfdi_type, "in_invoice")
        elif import_type == "issued":
            issued_move_type = {
                "I": "out_invoice",
                "E": "out_refund",
                "N": "entry",
                "P": "entry",
            }
            move_type = issued_move_type.get(cfdi_type, "out_invoice")
        return move_type

    def _get_serie_folio(self, cfdi_node):
        """:return:        Serie + Folio
        :rtype:         str
        """
        xml_serie = cfdi_node.get("Serie", False)
        xml_folio = cfdi_node.get("Folio", False)
        xml_sefo = ""
        if xml_serie or xml_folio:
            xml_sefo = "%s%s" % (
                cfdi_node.get("Serie", ""),
                cfdi_node.get("Folio", ""),
            )
        return xml_sefo

    def _get_datetime(self, cfdi_infos):
        """:return:        CFDI date
        :rtype:         datetime
        """
        date = cfdi_infos["emission_date_str"] or cfdi_infos["stamp_date"]
        return datetime.strptime(date, "%Y-%m-%d %H:%M:%S")

    def _get_payment_term_id(self, cfdi_node):
        """Get Payment Term ID from CFDI."""
        if conditions := cfdi_node.get("CondicionesDePago"):
            return self.env["account.payment.term"].search([("name", "=ilike", conditions)], limit=1).id
        return False

    def _get_payment_method_id(self, cfdi_node):
        """Get MX Payment Method ID from CFDI."""
        payment_form = cfdi_node.get("FormaDePago") or cfdi_node.get("FormaPago")
        return (
            self.env["l10n_mx_edi.payment.method"].search([("code", "=", payment_form)], limit=1).id
            or self.env.ref("l10n_mx_edi.payment_method_otros").id
        )

    def _get_currency_id(self, cfdi_node):
        """Get Currency ID from CFDI."""
        currency_code = cfdi_node.get("Moneda", "MXN")
        mxn = [
            "mxp",
            "mxn",
            "mn",
            "peso",
            "pesos",
            "peso mexicano",
            "pesos mexicanos",
            "nacional",
            "nal",
            "m.n.",
            "$",
            "2013",
        ]
        usd = ["dolar", "dólar", "dólares", "dolares"]
        currency_code = "MXN" if currency_code.lower() in mxn else currency_code
        currency_code = "USD" if currency_code.lower() in usd else currency_code

        return self.env["res.currency"].search([("name", "=", currency_code)], limit=1).id

    def _get_fuel_codes(self):
        """Return the codes that can be used in FUEL"""
        return [str(r) for r in range(15101500, 15101515)]

    def _get_expense_tax_names(self):
        """Some taxes are not found in the system, but is correct, because those
        taxes should be added in the invoice like expenses.
        To make dynamic this a system parameter can be added with the name:
        \"l10n_mx_taxes_for_expense\", then set the tax name. If many taxes split
        the names by \",\" """
        taxes = self.env["ir.config_parameter"].sudo().get_param("l10n_mx_taxes_for_expense", False)
        if taxes:
            return taxes.split(",")
        return ["ISH", "TUA", "ISAN"]

    def _get_tax_group_name(self, name, rate):
        """Construct tax group name for further search"""
        return f"{name} {rate}".replace(".0", "")

    def _get_tax_group(self, name, rate):
        """Return account.tax.group records"""
        tax_group_name = self._get_tax_group_name(name, rate)
        tax_group = (
            self.env["account.tax.group"].with_context(lang="es_MX").search([("name", "ilike", tax_group_name)])
        )
        return tax_group

    def _get_tax_name(self, name, rate):
        """Construct tax name for further search"""
        return f"{name} {rate}".replace(".0", "")

    def _get_tax_domain(self, name, amount, factor_type, type_tax_use="purchase"):
        """Construct tax domain for further search"""
        tax_name = self._get_tax_name(name, amount)
        domain = [
            ("company_id", "=", self.env.company.id),
            ("type_tax_use", "=", type_tax_use),
            ("name", "ilike", tax_name),
            ("l10n_mx_factor_type", "=", factor_type),
        ]
        if -10.67 <= amount <= -10.66:
            domain.append(("amount", "<=", -10.66))
            domain.append(("amount", ">=", -10.67))
        else:
            domain.append(("amount", "=", amount))
        return domain

    def collect_complemento(
        self,
        cfdi_node,
        attribute="TimbreFiscalDigital",
        namespace_uri=None,
    ):
        """Helper to extract relevant data from CFDI nodes.
        By default this method will retrieve tfd, Adjust parameters for other nodes
        :param cfdi_node:   XML node representing 'Comprobante' from CFDI.
        :param attribute:   tfd.
        :param namespaces:  tfd.
        :return:            A python dictionary.
        """
        if not namespace_uri:
            namespace_uri = "http://www.sat.gob.mx/TimbreFiscalDigital"
        xpath_expr = "//*[local-name()='Complemento']" "/*[local-name()='{}' and namespace-uri()='{}']".format(
            attribute, namespace_uri
        )
        try:
            node = cfdi_node.xpath(xpath_expr)
            return node[0] if node else None
        except Exception as e:
            _logger.error("Error extracting complemento %s: %s", attribute, str(e))
        return None

    def collect_taxes(self, tax_element):
        """Get tax data of the Impuesto node of the xml and return
        dictionary with taxes datas
        :param taxes_xml: Impuesto node of xml
        :type taxes_xml: etree
        :return: A list with the taxes data dict
        :rtype: list
        """
        tax_vals = []
        tax_codes = {"001": "ISR", "002": "IVA", "003": "IEPS"}
        for line in tax_element:
            att_tax = line.get("Impuesto", "")
            att_tax = tax_codes.get(att_tax, att_tax)
            att_rate = float_round(float(line.get("TasaOCuota", 0.0)) * 100, 4)
            att_amount = float(line.get("Importe", 0.0))
            att_factor = line.get("TipoFactor", "Tasa")
            if "Retenciones" in line.getparent().tag:
                att_amount = att_amount * -1
                att_rate = att_rate * -1
            tax_dict = {
                "name": att_tax,
                "amount": att_rate,
                "total": att_amount,
                "l10n_mx_factor_type": att_factor,
            }
            tax_vals.append(tax_dict)
        return tax_vals

    def collect_local_taxes(self, local_tax_node, attrs):
        local_tax_vals = []
        for tax in getattr(local_tax_node, attrs[0]):
            tax_dict = {
                "name": tax.get(attrs[1]),
                "amount": float(tax.get(attrs[2])) * 100 * attrs[3],
                "total": float(tax.get("Importe")) * attrs[3],
            }
            local_tax_vals.append(tax_dict)
        return local_tax_vals

    def partner_search_create(self, cfdi_node):
        partner_obj = self.env["res.partner"]
        emisor_node = cfdi_node.xpath("//*[local-name()='Emisor']")[0]
        name = emisor_node.get("Nombre", "")
        vat = emisor_node.get("Rfc", "")
        import_type = self._get_import_type(vat)
        if import_type == "issued":
            receptor_node = cfdi_node.xpath("//*[local-name()='Receptor']")[0]
            name = receptor_node.get("Nombre", "")
            vat = receptor_node.get("Rfc", "")
        partner = partner_obj.search([("vat", "=", vat)], limit=1, order="id asc")
        if not partner:
            partner = partner_obj.sudo().create(
                {
                    "company_type": "company",
                    "name": name,
                    "vat": vat,
                    "country_id": self.env.ref("base.mx").id,
                }
            )
            partner.message_post(
                body=self.env._(
                    "This partner was created when importing a CFDI file. Please verify that Partner data are correct."
                )
            )
        return partner

    def _prepare_local_taxes(self, local_taxes_node):
        """:param cfdi_etree:  The cfdi etree object.
        :return:            A list of python dictionaries.
        """
        local_taxes_vals = []
        if hasattr(local_taxes_node, "RetencionesLocales"):
            attrs = ["RetencionesLocales", "ImpLocRetenido", "TasadeRetencion", -1]
            local_taxes_vals = self.collect_local_taxes(local_taxes_node, attrs)
        if hasattr(local_taxes_node, "TrasladosLocales"):
            attrs = ["TrasladosLocales", "ImpLocTrasladado", "TasadeTraslado", 1]
            local_taxes_vals += self.collect_local_taxes(local_taxes_node, attrs)
        expense_taxes = self._get_expense_tax_names()
        local_taxes_lines = []
        for tax in local_taxes_vals:
            if tax["name"] in expense_taxes:
                local_taxes_lines.append(
                    Command.create(
                        {
                            "name": tax["name"],
                            "quantity": 1,
                            "price_unit": tax["total"],
                        },
                    )
                )
        return local_taxes_lines

    def _prepare_invoice_line_tax_ids(self, line):
        """Prepares tax IDs for an invoice line from CFDI tax data.

        Args:
            line (etree._Element): XML node representing 'Concepto' from CFDI

        Returns:
            list: IDs of account.tax to be applied to the invoice line
        """

        # Helper function to find taxes
        def find_taxes(tax_type):
            tax_attribute = "Traslado" if tax_type == "Traslados" else "Retencion"
            return line.findall("{*}Impuestos/{*}%s/{*}%s" % (tax_type, tax_attribute))

        # Collect all applicable taxes
        collected_taxes = []
        for tax_type in ["Traslados", "Retenciones"]:
            for tax_node in find_taxes(tax_type):
                collected_taxes.extend(self.collect_taxes([tax_node]))

        # Find matching taxes in the system
        tax_ids = []
        mx_taxes = self.env["account.tax"].with_context(lang="es_MX")

        for tax_data in collected_taxes:
            tax_domain = self._get_tax_domain(tax_data["name"], tax_data["amount"], tax_data["l10n_mx_factor_type"])
            existing_tax = mx_taxes.search(tax_domain, limit=1, order="id asc")
            if existing_tax:
                tax_ids.append(existing_tax.id)

        return tax_ids

    def _search_vehicle_ecc12(self, line_ecc12_element):
        domain_vehicle = [("fuel_card_name", "=", line_ecc12_element.get("Identificador"))]
        vehicle_exist = self.env["fleet.vehicle"].search(domain_vehicle, limit=1, order="id asc")
        return vehicle_exist

    def _search_partner_ecc12(self, line_ecc12_element):
        partner = self.env["res.partner"]
        partner_domain = [("vat", "=", line_ecc12_element.get("Rfc"))]
        partner_exist = partner.search(partner_domain, limit=1, order="id asc")
        if not partner_exist:
            partner_exist = partner.sudo().create(
                {
                    "name": line_ecc12_element.get("ClaveEstacion"),
                    "vat": line_ecc12_element.get("Rfc"),
                    "company_type": "company",
                    "country_id": self.env.ref("base.mx").id,
                }
            )
            msg = self.env._(
                "This partner was created when importing a CFDI file. Please verify that Partner datas are correct."
            )
            partner_exist.message_post(body=msg)
        return partner_exist

    def _prepare_ecc12_invoice_line_vals(self, ecc12_node):
        """Prepares invoice line values from ECC12 (Estado de Cuenta Combustible) CFDI complement.

        Args:
            ecc12_node (etree._Element): XML node of the ECC12 complement

        Returns:
            list: List of Command.create dictionaries for invoice lines
        """
        # Constants and reusable objects
        tax_obj = self.env["account.tax"].with_context(lang="es_MX")
        tax_exempt = tax_obj.search(
            [
                ("company_id", "=", self.env.company.id),
                ("type_tax_use", "=", "purchase"),
                ("name", "=ilike", "IVA exento"),
                ("amount_type", "=", "percent"),
                ("amount", "=", 0.0),
                ("l10n_mx_factor_type", "=", "Exento"),
            ],
            limit=1,
        )
        ns = {"ecc12": "http://www.sat.gob.mx/EstadoDeCuentaCombustible12"}
        invoice_lines = []

        # Process each fuel concept line
        for line in ecc12_node.findall("{*}Conceptos/{*}ConceptoEstadoDeCuentaCombustible", namespaces=ns):
            # Base data extraction
            partner = self._search_partner_ecc12(line)
            vehicle = self._search_vehicle_ecc12(line)
            quantity = float(line.get("Cantidad", 0.0))
            total_amount = float(line.get("Importe", 0.0))

            # Tax processing
            tax_ids = []
            ieps_amount = 0.0
            price_unit = float(line.get("ValorUnitario", 0.0))

            # Get and process taxes if they exist
            tax_nodes = line.findall("{*}Traslados/{*}Traslado", namespaces=ns)
            if tax_nodes:
                taxes = self.collect_taxes(tax_nodes)
                ieps_taxes = [t for t in taxes if t.get("tax") == "IEPS"]
                other_taxes = [t for t in taxes if t.get("tax") != "IEPS"]

                # Process main tax (non-IEPS)
                if other_taxes:
                    main_tax = other_taxes[0]
                    tax_domain = self._get_tax_domain(
                        main_tax["name"],
                        main_tax["amount"],
                        main_tax["l10n_mx_factor_type"],
                    )
                    existing_tax = tax_obj.search(tax_domain, limit=1, order="id asc")
                    if existing_tax:
                        tax_ids.append(existing_tax.id)
                        price_unit = round(main_tax.get("total", 0.0) / (main_tax.get("amount", 100) / 100), 2)

                # Process IEPS tax if exists
                if ieps_taxes:
                    ieps_amount = float(ieps_taxes[0].get("amount", 0.0))

            # Main fuel line
            invoice_lines.append(
                Command.create(
                    {
                        "name": self.env._(
                            "Identifier: %s - Operation: %s - Station: %s",
                            line.get("Identificador"),
                            line.get("FolioOperacion"),
                            line.get("ClaveEstacion"),
                        ),
                        "vehicle_id": vehicle.id or False,
                        "quantity": quantity,
                        "price_unit": price_unit / quantity if quantity else 0.0,
                        "tax_ids": [Command.set(tax_ids)] if tax_ids else False,
                        "partner_id": partner.id,
                    }
                )
            )

            # IEPS line if applicable
            if tax_nodes:  # Only add IEPS line if there were taxes
                invoice_lines.append(
                    Command.create(
                        {
                            "name": self.env._("Fuel - IEPS"),
                            "vehicle_id": vehicle.id or False,
                            "quantity": 1.0,
                            "price_unit": (total_amount - price_unit) + ieps_amount,
                            "tax_ids": [Command.set([tax_exempt.id])] if tax_exempt else False,
                            "partner_id": partner.id,
                        }
                    )
                )

        return invoice_lines

    def _prepare_invoice_line_vals(self, cfdi_node, can_create_product=False, partner=None):
        """Prepare invoice line values from CFDI concept nodes.

        Args:
            cfdi_node (etree._Element): The CFDI XML node containing concept lines
            can_create_product (bool, optional): Whether to create missing products.
                Defaults to False.
            partner (res.partner, optional): Partner to use for product search context.
                Defaults to None.

        Returns:
            list: List of Command.create dictionaries ready for invoice_line_ids, each containing:
                - 'name': Line description
                - 'product_id': Product ID (if found/created)
                - 'quantity': Product quantity
                - 'product_uom_id': Unit of measure ID
                - 'price_unit': Unit price
                - 'discount': Discount percentage
                - 'tax_ids': List of tax IDs applicable to the line
                Additional fields for special cases like fuel lines.

        Notes:
            - Handles both regular products and special cases like fuel (IEPS)
            - Automatically processes global discounts if present in CFDI
            - Creates products on-the-fly if can_create_product=True
            - Matches UoM (Unit of Measure) using UNSPSC codes from CFDI
            - Processes both regular taxes and local taxes from complementos
        """
        ns = {"cfdi": "http://www.sat.gob.mx/cfd/4"}

        def get_product_sat_code(unspsc_code):
            return self.env["product.unspsc.code"].search(
                [
                    ("code", "=", unspsc_code),
                    ("applies_to", "=", "product"),
                ],
                limit=1,
            )

        global_discount = float(cfdi_node.get("Descuento", 0))
        global_line_discount = 0
        if global_discount:
            global_line_discount = global_discount * 100 / float(cfdi_node.get("SubTotal", 0.0))
        invoice_lines = []
        for line in cfdi_node.findall("{*}Conceptos/{*}Concepto", namespaces=ns):
            uom_unspsc_code = self.env["product.unspsc.code"].search(
                [
                    ("code", "=", line.get("ClaveUnidad", "")),
                    ("applies_to", "=", "uom"),
                ],
                limit=1,
            )
            uom_domain = [("unspsc_code_id", "=", uom_unspsc_code.id)]
            uom = self.env.ref("uom.product_uom_unit")
            prefetch_uom = self.env["uom.uom"].with_context(lang="es_MX").search(uom_domain)
            if prefetch_uom and len(prefetch_uom) == 1:
                uom = prefetch_uom
            elif prefetch_uom and len(prefetch_uom) > 1:
                uom_domain.append(("name", "=ilike", line.get("Unidad", "")))
                uom = self.env["uom.uom"].with_context(lang="es_MX").search(uom_domain, limit=1) or uom

            product_code = line.get("NoIdentificacion")  # default_code if export from Odoo
            unspsc_code = line.get("ClaveProdServ")  # UNSPSC code
            description = line.get("Descripcion")  # label of the invoice line "[{p.default_code}] {p.name}"
            cleaned_name = re.sub(
                r"^\[.*\] ",
                "",
                description.splitlines()[0] if description.splitlines() else description,
            )
            product = self.env["product.product"]._retrieve_product(
                name=cleaned_name,
                default_code=product_code,
                extra_domain=[("unspsc_code_id.code", "=", unspsc_code)],
                company=self.env.company.id,
                vendor=partner,
            )
            if not product:
                product = self.env["product.product"]._retrieve_product(name=cleaned_name, default_code=product_code)

            line_discount = 0.0
            if global_line_discount:
                line_discount = global_line_discount
            elif line.get("Descuento"):
                line_discount = (float(line.get("Descuento")) / float(line.get("Importe", "0.0"))) * 100

            if not product and can_create_product:
                product = product.create(
                    {
                        "name": cleaned_name,
                        "description_purchase": cleaned_name,
                        "list_price": float(line.get("ValorUnitario")),
                        "type": "consu",
                        "is_storable": True,
                        "uom_id": uom.id,
                        "uom_po_id": uom.id,
                        "l10n_mx_edi_code_sat_id": get_product_sat_code(unspsc_code).id,
                    }
                )
            invoice_lines.append(
                Command.create(
                    {
                        "name": cleaned_name,
                        "product_id": product.id or False,
                        "quantity": float(line.get("Cantidad")),
                        "product_uom_id": product.uom_id.id if product else uom.id,
                        "price_unit": float(line.get("ValorUnitario")),
                        "discount": line_discount,
                        "tax_ids": [Command.set(self._prepare_invoice_line_tax_ids(line))],
                    },
                )
            )

            # Case for fuel move line
            if unspsc_code in self._get_fuel_codes():
                tax_node = line.findall("{*}Impuestos/{*}Traslados/{*}Traslado")
                tax = self.collect_taxes(tax_node)
                fuel_line_price = tax[0].get("amount") / (tax[0].get("rate") / 100)
                invoice_lines.append(
                    Command.create(
                        {
                            "name": self.env._("Fuel - IEPS"),
                            "quantity": 1,
                            "price_unit": float(line.get("Importe")) - fuel_line_price,
                        },
                    )
                )

        return invoice_lines

    def _prepare_invoice_vals(self, cfdi_infos, journal=False):
        """Prepare the dictionary of values to create a new invoice from CFDI data.

        Args:
            cfdi_infos (dict): Dictionary containing CFDI information with:
                - 'cfdi_node' (etree._Element): The root node of the CFDI XML
                - 'supplier_rfc' (str): The RFC of the supplier
                - 'payment_method' (str): The payment method code
                - 'usage' (str): The CFDI usage code
                - 'origin' (str): The origin reference if applicable
                - 'amount_total' (float): The total amount of the CFDI
            journal (account.journal, optional): Journal to use for the invoice.
                If not provided, will be determined automatically based on move type.

        Returns:
            dict: Dictionary of values ready to be passed to account.move.create(), containing:
                - 'move_type': The invoice type (in_invoice, out_invoice, etc.)
                - 'journal_id': The journal ID
                - 'currency_id': The currency ID
                - 'invoice_date': The invoice date
                - 'invoice_payment_term_id': Payment term ID if specified in CFDI
                - 'partner_id': Partner ID (created if doesn't exist)
                - 'name': Invoice number from Serie+Folio or '/'
                - 'payment_reference': Payment reference if received invoice
                - 'posted_before': True if issued invoice
                - Various l10n_mx_edi specific fields
                - 'x_check_tax': Total taxes amount for validation
                - 'x_check_total': Total amount for validation
                - 'invoice_line_ids': List of invoice line commands

        Raises:
            UserError: If required CFDI data is missing or invalid
        """
        move_obj = self.env["account.move"]
        move_type = self._get_move_type(cfdi_infos)
        import_type = self._get_import_type(cfdi_infos["supplier_rfc"])
        if not journal:
            journal_types = ["general"]
            if move_type in move_obj.get_sale_types():
                journal_types = ["sale"]
            elif move_type in move_obj.get_purchase_types():
                journal_types = ["purchase"]
            domain = [
                ("company_id", "=", self.env.company.id),
                ("type", "in", journal_types),
            ]
            journal = self.env["account.journal"].search(domain, limit=1, order="id asc")
        cfdi_node = cfdi_infos["cfdi_node"]
        partner = self.partner_search_create(cfdi_node)
        invoice_lines = []
        ecc12_node = self.collect_complemento(
            cfdi_node,
            "EstadoDeCuentaCombustible",
            "http://www.sat.gob.mx/EstadoDeCuentaCombustible12",
        )
        if ecc12_node is not None:
            invoice_lines.extend(self._prepare_ecc12_invoice_line_vals(ecc12_node))
        else:
            invoice_lines.extend(self._prepare_invoice_line_vals(cfdi_node, partner=partner))
            if local_taxes_node := self.collect_complemento(
                cfdi_node, "ImpuestosLocales", "http://www.sat.gob.mx/implocal"
            ):
                invoice_lines.extend(self._prepare_local_taxes(local_taxes_node))
        taxes_node = cfdi_node.find("{*}Impuestos") if hasattr(cfdi_node, "find") else None
        taxes_amount = float(taxes_node.get("TotalImpuestosTrasladados", 0.0)) if taxes_node is not None else 0.0
        vals = {
            "move_type": move_type,
            "journal_id": journal.id,
            "currency_id": self._get_currency_id(cfdi_node),
            "invoice_date": self._get_datetime(cfdi_infos),
            "invoice_payment_term_id": self._get_payment_term_id(cfdi_node),  # immediate
            "partner_id": partner.id,
            "name": self._get_serie_folio(cfdi_node) if import_type == "issued" else "/",
            "payment_reference": self._get_serie_folio(cfdi_node) if import_type == "received" else False,
            "posted_before": import_type == "issued",
            "l10n_mx_edi_payment_method_id": self._get_payment_method_id(cfdi_node),
            "l10n_mx_edi_payment_policy": cfdi_infos["payment_method"],
            "l10n_mx_edi_usage": cfdi_infos["usage"],
            "l10n_mx_edi_post_time": self._get_datetime(cfdi_infos),
            "l10n_mx_edi_cfdi_origin": cfdi_infos["origin"],
            "x_check_tax": taxes_amount,
            "x_check_total": cfdi_infos["amount_total"],
            "invoice_line_ids": invoice_lines,
        }
        return vals

    def get_headers(self, soap_action, token=False, condition=True):
        headers = {
            "SOAPAction": soap_action,
            "Content-type": 'text/xml; charset="utf-8"',
            "Accept": "text/xml",
        }
        if condition:
            headers.update(
                {
                    "Cache-Control": "no-cache",
                    "Authorization": f'WRAP access_token="{token}"' if token else "",
                }
            )
        return headers

    def check_comm(self, url, data, headers, result_xpath, external_nsmap):
        try:
            communication = requests.post(
                url,
                data,
                headers=headers,
                verify=True,
                timeout=20,
            )
            response = etree.fromstring(communication.text)
        except etree.XMLSyntaxError as e:
            _logger.error(str(e))
            raise ValidationError(str(e))

        except Exception as e:
            _logger.error(str(e))
            raise ValidationError(str(e))

        if communication.status_code != requests.codes.ok:
            error = response.find(".//faultstring").text
            raise ValidationError(error)

        return response.find(result_xpath, external_nsmap)

    def prepare_soap_data(
        self,
        certificate: crypto.X509,
        private_key: crypto.PKey,
        arguments: dict,
        envelop: str,
        xpath: str,
        token=False,
    ):
        internal_nsmap = {
            "": "http://www.w3.org/2000/09/xmldsig#",
            "s": "http://schemas.xmlsoap.org/soap/envelope/",
            "u": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd",
            "o": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd",
            "des": "http://DescargaMasivaTerceros.sat.gob.mx",
        }
        parser = etree.XMLParser(remove_blank_text=True)
        element_root = etree.fromstring(envelop, parser)
        element = element_root.find(xpath, internal_nsmap)
        signature = """
            <Signature xmlns="http://www.w3.org/2000/09/xmldsig#">
                <SignedInfo>
                    <CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                    <SignatureMethod Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1"/>
                    <Reference URI="#_0">
                        <Transforms>
                            <Transform Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
                        </Transforms>
                        <DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>
                        <DigestValue></DigestValue>
                    </Reference>
                </SignedInfo>
                <SignatureValue></SignatureValue>
            </Signature>
        """
        element_signature = etree.fromstring(signature, parser)
        element_to_digest = element_root.find(".//u:Timestamp", internal_nsmap)
        if not etree.iselement(element_to_digest):
            element_to_digest = element.getparent()
            for key in arguments:
                if key == "RfcReceptores":
                    for i, rfc_receptor in enumerate(arguments[key]):
                        if not i:
                            element_receptor = element_root.find(".//des:RfcReceptor", internal_nsmap)
                            element_receptor.text = rfc_receptor
                    continue

                if arguments[key] is not None:
                    element.set(key, arguments[key])

        digest_value = element_signature.find(".//DigestValue", internal_nsmap)
        digest_value.text = base64.b64encode(
            hashlib.sha1(etree.tostring(element_to_digest, method="c14n", exclusive=1)).digest()
        )
        element_to_sign = element_signature.find(".//SignedInfo", internal_nsmap)
        element_to_sign = etree.tostring(element_to_sign, method="c14n", exclusive=1)
        element_signed = element_signature.find(".//SignatureValue", internal_nsmap)
        element_signed.text = (
            base64.b64encode(crypto.sign(private_key, element_to_sign, "sha1")).decode("UTF-8").replace("\n", "")
        )

        if not token:
            key_info = """
                <KeyInfo xmlns:o="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
                    <o:SecurityTokenReference>
                        <o:Reference URI="#{uuid}" ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"/>
                    </o:SecurityTokenReference>
                </KeyInfo>
                """.format(
                **arguments
            )
        else:
            key_info = """
                <KeyInfo>
                    <X509Data>
                        <X509IssuerSerial>
                            <X509IssuerName></X509IssuerName>
                            <X509SerialNumber></X509SerialNumber>
                        </X509IssuerSerial>
                        <X509Certificate></X509Certificate>
                    </X509Data>
                </KeyInfo>
            """
        element_key_info = etree.fromstring(key_info, parser)
        if not token:
            element_certificate = element_root.find(".//o:BinarySecurityToken", internal_nsmap)
            element_certificate.text = base64.b64encode(crypto.dump_certificate(crypto.FILETYPE_ASN1, certificate))
        else:
            element_certificate = element_key_info.find(".//X509Certificate")
            element_certificate.text = base64.b64encode(crypto.dump_certificate(crypto.FILETYPE_ASN1, certificate))
            cer_issuer = certificate.get_issuer().get_components()
            cer_issuer = ",".join(
                ["{key}={value}".format(key=key.decode(), value=value.decode()) for key, value in cer_issuer]
            )
            element_issuer_name = element_key_info.find(".//X509IssuerName")
            element_issuer_name.text = cer_issuer
            element_serial_number = element_key_info.find(".//X509SerialNumber")
            element_serial_number.text = str(certificate.get_serial_number())

        element_signature.append(element_key_info)
        element.append(element_signature)
        return etree.tostring(element_root, method="c14n", exclusive=1)

    def l10n_mx_ws_get_cfdi_status(self, emmiter_vat, receiver_vat, total, uuid):
        expression = "?re=%s&amp;rr=%s&amp;tt=%s&amp;id=%s" % (
            tools.html_escape(emmiter_vat or ""),
            tools.html_escape(receiver_vat or ""),
            total or 0.0,
            uuid or "",
        )
        data = f"""
            <?xml version="1.0" encoding="UTF-8"?>
            <s:Envelope
                xmlns:ns0="http://tempuri.org/"
                xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
                <s:Header/>
                <s:Body>
                    <ns0:Consulta>
                        <ns0:expresionImpresa>${expression}</ns0:expresionImpresa>
                    </ns0:Consulta>
                </s:Body>
            </s:Envelope>
        """
        url = "https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc?wsdl"
        soap_action = "http://tempuri.org/IConsultaCFDIService/Consulta"
        headers = self.get_headers(soap_action, condition=False)
        result_xpath = "s:Body/ConsultaResponse/ConsultaResult"
        external_nsmap = {
            "": "http://tempuri.org/",
            "a": "http://schemas.datacontract.org/2004/07/Sat.Cfdi.Negocio.ConsultaCfdi.Servicio",
            "i": "http://www.w3.org/2001/XMLSchema-instance",
            "s": "http://schemas.xmlsoap.org/soap/envelope/",
        }
        communication = self.check_comm(url, data, headers, result_xpath, external_nsmap)
        ret_dict = {
            "status": communication.find("a:Estado", external_nsmap).text,
            "is_cancellable": communication.find("a:EsCancelable", external_nsmap).text,
            "cancel_status": communication.find("a:EstatusCancelacion", external_nsmap).text,
            "efos_validation": communication.find("a:ValidacionEFOS", external_nsmap).text,
        }
        return ret_dict

    def l10n_mx_ws_generate_token(self, certificate, private_key, uuid=None):
        date_created = datetime.utcnow()
        date_expires = date_created + timedelta(seconds=300)
        date_created = date_created.isoformat()
        date_expires = date_expires.isoformat()
        envelop = f"""
            <s:Envelope
                xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
                xmlns:u="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
                xmlns:o="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
                <s:Header>
                    <o:Security s:mustUnderstand="1">
                        <u:Timestamp u:Id="_0">
                            <u:Created>{date_created}</u:Created>
                            <u:Expires>{date_expires}</u:Expires>
                        </u:Timestamp>
                        <o:BinarySecurityToken
                            u:Id="uuid-{uuid}-4"
                            ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"
                            EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">
                        </o:BinarySecurityToken>
                    </o:Security>
                </s:Header>
                <s:Body>
                <Autentica xmlns="http://DescargaMasivaTerceros.gob.mx"/>
                </s:Body>
            </s:Envelope>
        """
        xpath = "s:Header/o:Security"
        data = self.prepare_soap_data(certificate, private_key, {"uuid": f"uuid-{uuid}-4"}, envelop, xpath, False)
        url = "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/Autenticacion/Autenticacion.svc"
        soap_action = "http://DescargaMasivaTerceros.gob.mx/IAutenticacion/Autentica"
        headers = self.get_headers(soap_action)
        result_xpath = "s:Body/AutenticaResponse/AutenticaResult"
        external_nsmap = {
            "": "http://DescargaMasivaTerceros.gob.mx",
            "s": "http://schemas.xmlsoap.org/soap/envelope/",
            "u": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd",
            "o": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd",
        }
        communication = self.check_comm(url, data, headers, result_xpath, external_nsmap)
        ret_dict = {
            "expires": date_expires,
            "token": communication.text,
        }
        return ret_dict

    def sanitize_args(self, args):
        args_allowed = (
            "uuid",
            "emitter_vat",
            "receiver_vats",
            "request_type",
            "date_from",
            "date_to",
            "cfdi_type",
            "cfdi_state",
            "thirthparty_vat",
            "complement",
        )
        sanitized_arg = {}
        for key, value in args.items():
            if key in args_allowed:
                sanitized_arg[key] = value
        return sanitized_arg

    def l10n_mx_ws_request_download(self, certificate, private_key, token, args):
        if not isinstance(args, dict):
            raise ValidationError(self.env._("Validation error"))

        holder_vat = "".join(certificate.get_subject().x500UniqueIdentifier.split(" ")[0])
        sanitized = self.sanitize_args(args)
        arguments = {
            "UUID": sanitized["uuid"] if "uuid" in sanitized else None,
            "RfcSolicitante": holder_vat,
            "RfcEmisor": (
                sanitized["emitter_vat"] if "emitter_vat" in sanitized and "uuid" not in sanitized else None
            ),
            "RfcReceptores": (
                sanitized["receiver_vats"]
                if "receiver_vats" in sanitized and "uuid" not in sanitized
                else [holder_vat]
            ),
            "FechaInicial": (sanitized["date_from"].isoformat() if "date_from" in sanitized else None),
            "FechaFinal": (sanitized["date_to"].isoformat() if "date_to" in sanitized else None),
            "TipoSolicitud": (sanitized["request_type"] if "request_type" in sanitized else "CFDI"),
            "TipoComprobante": (
                sanitized["cfdi_type"] if "cfdi_type" in sanitized and "uuid" not in sanitized else None
            ),
            "EstadoComprobante": (
                sanitized["cfdi_state"] if "cfdi_state" in sanitized and "uuid" not in sanitized else None
            ),
            "RfcACuentaTerceros": (
                sanitized["thirthparty_vat"] if "thirthparty_vat" in sanitized and "uuid" not in sanitized else None
            ),
            "Complemento": (
                sanitized["complement"] if "complement" in sanitized and "uuid" not in sanitized else None
            ),
        }
        envelop = """
            <s:Envelope
                xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
                xmlns:des="http://DescargaMasivaTerceros.sat.gob.mx">
                <s:Header/>
                <s:Body>
                    <des:SolicitaDescarga>
                        <des:solicitud>
                            <des:RfcReceptores>
                                <des:RfcReceptor/>
                                </des:RfcReceptores>
                        </des:solicitud>
                    </des:SolicitaDescarga>
                </s:Body>
            </s:Envelope>
        """
        xpath = "s:Body/des:SolicitaDescarga/des:solicitud"
        data = self.prepare_soap_data(certificate, private_key, arguments, envelop, xpath, token)
        url = "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/SolicitaDescargaService.svc"
        soap_action = "http://DescargaMasivaTerceros.sat.gob.mx/ISolicitaDescargaService/SolicitaDescarga"
        headers = self.get_headers(soap_action, token)
        result_xpath = "s:Body/SolicitaDescargaResponse/SolicitaDescargaResult"
        external_nsmap = {
            "": "http://DescargaMasivaTerceros.sat.gob.mx",
            "s": "http://schemas.xmlsoap.org/soap/envelope/",
            "u": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd",
            "o": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd",
            "h": "http://DescargaMasivaTerceros.sat.gob.mx",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xsd": "http://www.w3.org/2001/XMLSchema",
        }
        communication = self.check_comm(url, data, headers, result_xpath, external_nsmap)
        ret_dict = {
            "id_solicitud": communication.get("IdSolicitud"),
            "cod_estatus": communication.get("CodEstatus"),
            "mensaje": communication.get("Mensaje"),
        }
        return ret_dict

    def l10n_mx_ws_verify_package(self, certificate, private_key, token, id_solicitud):
        arguments = {
            "RfcSolicitante": certificate.get_subject().x500UniqueIdentifier.split(" ")[0],
            "IdSolicitud": id_solicitud,
        }
        envelop = """
            <s:Envelope
                xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
                xmlns:des="http://DescargaMasivaTerceros.sat.gob.mx">
                <s:Header/>
                <s:Body>
                    <des:VerificaSolicitudDescarga>
                        <des:solicitud IdSolicitud="" RfcSolicitante="" />
                    </des:VerificaSolicitudDescarga>
                </s:Body>
            </s:Envelope>
        """
        xpath = "s:Body/des:VerificaSolicitudDescarga/des:solicitud"
        data = self.prepare_soap_data(certificate, private_key, arguments, envelop, xpath, token)
        url = "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/VerificaSolicitudDescargaService.svc"
        soap_action = (
            "http://DescargaMasivaTerceros.sat.gob.mx/IVerificaSolicitudDescargaService/VerificaSolicitudDescarga"
        )
        headers = self.get_headers(soap_action, token)
        external_nsmap = {
            "": "http://DescargaMasivaTerceros.sat.gob.mx",
            "s": "http://schemas.xmlsoap.org/soap/envelope/",
            "u": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd",
            "o": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd",
            "h": "http://DescargaMasivaTerceros.sat.gob.mx",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xsd": "http://www.w3.org/2001/XMLSchema",
        }
        result_xpath = "s:Body/VerificaSolicitudDescargaResponse/VerificaSolicitudDescargaResult"
        communication = self.check_comm(url, data, headers, result_xpath, external_nsmap)
        ret_dict = {
            "cod_estatus": communication.get("CodEstatus"),
            "estado_solicitud": communication.get("EstadoSolicitud"),
            "codigo_estado_solicitud": communication.get("CodigoEstadoSolicitud"),
            "numero_cfdis": communication.get("NumeroCFDIs"),
            "mensaje": communication.get("Mensaje"),
            "paquetes": [],
        }
        for id_paquete in communication.iter("{{{}}}IdsPaquetes".format(external_nsmap[""])):
            ret_dict["paquetes"].append(id_paquete.text)
        return ret_dict

    def l10n_mx_ws_download_package(self, certificate, private_key, token, id_paquete):
        arguments = {
            "RfcSolicitante": certificate.get_subject().x500UniqueIdentifier.split(" ")[0],
            "IdPaquete": id_paquete,
        }
        envelop = """
            <s:Envelope
                xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
                xmlns:des="http://DescargaMasivaTerceros.sat.gob.mx">
                <s:Header/>
                <s:Body>
                    <des:PeticionDescargaMasivaTercerosEntrada>
                        <des:peticionDescarga IdPaquete="" RfcSolicitante=""/>
                    </des:PeticionDescargaMasivaTercerosEntrada>
                </s:Body>
            </s:Envelope>
        """
        xpath = "s:Body/des:PeticionDescargaMasivaTercerosEntrada/des:peticionDescarga"
        data = self.prepare_soap_data(certificate, private_key, arguments, envelop, xpath, token)
        url = "https://cfdidescargamasiva.clouda.sat.gob.mx/DescargaMasivaService.svc"
        soap_action = "http://DescargaMasivaTerceros.sat.gob.mx/IDescargaMasivaTercerosService/Descargar"
        headers = self.get_headers(soap_action, token)
        external_nsmap = {
            "": "http://DescargaMasivaTerceros.sat.gob.mx",
            "s": "http://schemas.xmlsoap.org/soap/envelope/",
            "u": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd",
            "o": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd",
            "h": "http://DescargaMasivaTerceros.sat.gob.mx",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xsd": "http://www.w3.org/2001/XMLSchema",
        }
        result_xpath = "s:Body/RespuestaDescargaMasivaTercerosSalida/Paquete"
        communication = self.check_comm(url, data, headers, result_xpath, external_nsmap)
        respuesta = (
            communication.getparent().getparent().getparent().find("s:Header/h:respuesta", namespaces=external_nsmap)
        )
        ret_dict = {
            "cod_estatus": respuesta.get("CodEstatus"),
            "mensaje": respuesta.get("Mensaje"),
            "paquete_b64": communication.text,
        }
        return ret_dict
