import base64
import hashlib
import logging
import requests

from datetime import datetime, timedelta
from lxml import etree, objectify
from OpenSSL import crypto

from odoo import models, tools
from odoo.exceptions import ValidationError
from odoo.fields import Command
from odoo.tools.float_utils import float_round
from odoo.tools.translate import _

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

    def _xml2capitalize(self, xml):
        """Receive 1 lxml etree object and change all attrib to Capitalize."""

        def recursive_lxml(element):
            for attrib, value in element.attrib.items():
                new_attrib = "%s%s" % (attrib[0].upper(), attrib[1:])
                element.attrib.update({new_attrib: value})
            for child in element.getchildren():
                child = recursive_lxml(child)
            return element

        return recursive_lxml(xml)

    def _convert_cfdi32_to_cfdi33(self, cfdi_etree):
        """Convert a xml from cfdi32 to cfdi33
        :param xml: The xml 32 in lxml.objectify object
        :return: A xml 33 in lxml.objectify object
        """
        if cfdi_etree.get("Version") in ("3.3", "4.0"):
            return cfdi_etree
        cfdi_etree = self._xml2capitalize(cfdi_etree)
        cfdi_etree.attrib.update(
            {
                "TipoDeComprobante": TYPE_CFDI22_TO_CFDI33[
                    cfdi_etree.attrib["tipoDeComprobante"]
                ],
                "MetodoPago": "PPD",
            }
        )
        return cfdi_etree

    def check_objectify_xml(self, xml64):
        """Helper to decode and lxml objectify an xml b64 file.
        :param xml64:       An xml b64 file.
        :return:            etree object or False
        :rtype:             etree object or False
        """
        cfdi_etree = False
        try:
            if isinstance(xml64, bytes):
                xml64 = xml64.decode()
            xml_str = base64.b64decode(xml64)
            objectify.fromstring(xml_str)
        except etree.XMLSyntaxError as e:
            _logger.warning(str(e))
            return cfdi_etree

        xml_str = (
            xml_str.replace(b"xmlns:schemaLocation", b"xsi:schemaLocation")
            .replace(b"data:text/xml;base64,", b"")
            .replace(b"o;?", b"")
            .replace(b"\xef\xbf\xbd", b"")
        )
        cfdi_etree = objectify.fromstring(xml_str)
        return cfdi_etree

    def collect_complemento(
        self,
        cfdi_etree,
        attribute="tfd:TimbreFiscalDigital[1]",
        namespaces=None,
    ):
        """Helper to extract relevant data from CFDI nodes.
        By default this method will retrieve tfd, Adjust parameters for other nodes
        :param cfdi_etree:  The cfdi etree object.
        :param attribute:   tfd.
        :param namespaces:  tfd.
        :return:            A python dictionary.
        """
        if not namespaces:
            namespaces = {"tfd": "http://www.sat.gob.mx/TimbreFiscalDigital"}
        if not hasattr(cfdi_etree, "Complemento"):
            return None
        node = cfdi_etree.Complemento.xpath(attribute, namespaces=namespaces)
        return node[0] if node else None

    def get_import_type(self, cfdi_etree):
        import_type = (
            "issued"
            if self.env.company.vat == cfdi_etree.Emisor.get("Rfc", "")
            else "received"
        )
        cfdi_type = cfdi_etree.get("TipoDeComprobante", False)
        move_type = None
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
        return import_type, move_type

    def get_serie_folio(self, cfdi_etree):
        """:return:        Serie + Folio
        :rtype:         str
        """
        xml_serie = cfdi_etree.get("Serie", False)
        xml_folio = cfdi_etree.get("Folio", False)
        xml_sefo = ""
        if xml_serie or xml_folio:
            xml_sefo = "%s%s" % (
                cfdi_etree.get("Serie", ""),
                cfdi_etree.get("Folio", ""),
            )
        return xml_sefo

    def get_datetime(self, cfdi_etree):
        """:return:        CFDI date
        :rtype:         datetime
        """
        date = cfdi_etree.get("Fecha", cfdi_etree.get("FechaTimbrado", ""))
        return datetime.strptime(date, "%Y-%m-%dT%H:%M:%S")

    def get_currency(self, cfdi_etree):
        """:return:        Currency in ISO? code
        :rtype:         str
        """
        currency = cfdi_etree.get("Moneda", "MXN")
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
        currency = "MXN" if currency.lower() in mxn else currency
        currency = "USD" if currency.lower() in usd else currency
        return currency

    def get_related_uuids_dict(self, cfdi_etree):
        """:return:        {"type": TipoRelacion code, "uuids": []}
        :rtype:         dict
        """
        res = {
            "type": cfdi_etree.CfdiRelacionados.get("TipoRelacion", "01"),
            "uuids": [],
        }
        for related_uuid in cfdi_etree.CfdiRelacionados.CfdiRelacionado:
            res["uuids"].append(related_uuid.get("UUID").upper())
        return res

    def get_fuel_codes(self):
        """Return the codes that can be used in FUEL"""
        return [str(r) for r in range(15101500, 15101515)]

    def get_taxes_to_omit(self):
        """Some taxes are not found in the system, but is correct, because those
        taxes should be added in the invoice like expenses.
        To make dynamic this a system parameter can be added with the name:
        \"l10n_mx_taxes_for_expense\", then set the tax name. If many taxes split
        the names by \",\" """
        taxes = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("l10n_mx_taxes_for_expense", False)
        )
        if taxes:
            return taxes.split(",")
        return ["ISH", "TUA", "ISAN"]

    def prepare_search_tax_group_name(self, name, rate):
        """Construct tax group name for further search"""
        return f"{name} {rate}".replace(".0", "")

    def prepare_tax_group(self, name, rate):
        """Return account.tax.group records"""
        tax_group_name = self.prepare_search_tax_group_name(name, rate)
        tax_group = (
            self.env["account.tax.group"]
            .with_context(lang="es_MX")
            .search([("name", "ilike", tax_group_name)])
        )
        return tax_group

    def prepare_search_tax_name(self, name, rate):
        """Construct tax name for further search"""
        return f"{name} {rate}".replace(".0", "")

    def prepare_tax_domain(
        self, name, amount, l10n_mx_factor_type, type_tax_use="purchase"
    ):
        """Construct tax domain for further search"""
        tax_name = self.prepare_search_tax_name(name, amount)
        domain = [
            ("company_id", "=", self.env.company.id),
            ("active", "=", True),
            ("type_tax_use", "=", type_tax_use),
            ("name", "ilike", tax_name),
            ("l10n_mx_factor_type", "=", l10n_mx_factor_type),
        ]
        # tax_group = self.prepare_tax_group(name, rate)
        # if tax_group:
        #     domain.append(("tax_group_id", "in", tax_group.ids))
        if -10.67 <= amount <= -10.66:
            domain.append(("amount", "<=", -10.66))
            domain.append(("amount", ">=", -10.67))
        else:
            domain.append(("amount", "=", amount))
        return domain

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

    def prepare_line_tax_ids(self, line):
        collected_tax_vals = []
        if not hasattr(line, "Impuestos"):
            return collected_tax_vals
        if hasattr(line.Impuestos, "Traslados"):
            collected_tax_vals = self.collect_taxes(line.Impuestos.Traslados.Traslado)
        if hasattr(line.Impuestos, "Retenciones"):
            collected_tax_vals += self.collect_taxes(
                line.Impuestos.Retenciones.Retencion
            )
        tax_ids = []
        for tax in collected_tax_vals:
            tax_domain = self.prepare_tax_domain(
                tax["name"], tax["amount"], tax["l10n_mx_factor_type"]
            )
            tax_exist = (
                self.env["account.tax"]
                .with_context(lang="es_MX")
                .search(tax_domain, limit=1, order="id asc")
            )
            if tax_exist:
                tax_ids.append(tax_exist.id)
        return tax_ids

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

    def prepare_local_taxes(self, local_taxes_node):
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
        taxes_to_omit = self.get_taxes_to_omit()
        local_taxes_lines = []
        for tax in local_taxes_vals:
            if tax["name"] in taxes_to_omit:
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

    def search_vehicle_ecc12(self, line_ecc12_element):
        domain_vehicle = [
            ("fuel_card_name", "=", line_ecc12_element.get("Identificador"))
        ]
        vehicle_exist = self.env["fleet.vehicle"].search(
            domain_vehicle, limit=1, order="id asc"
        )
        return vehicle_exist

    def search_partner_ecc12(self, line_ecc12_element):
        partner_obj = self.env["res.partner"]
        domain_partner = [("vat", "=", line_ecc12_element.get("Rfc"))]
        partner_exist = partner_obj.search(domain_partner, limit=1, order="id asc")
        if not partner_exist:
            partner_exist = partner_obj.sudo().create(
                {
                    "name": line_ecc12_element.get("ClaveEstacion"),
                    "vat": line_ecc12_element.get("Rfc"),
                    "company_type": "company",
                    "country_id": self.env.ref("base.mx").id,
                }
            )
            msg = _(
                "This partner was created when importing a CFDI file. Please verify that Partner datas are correct."
            )
            partner_exist.message_post(body=msg)
        return partner_exist

    def prepare_invoice_lines_ecc12(self, ecc12_node):
        tax_exempt = (
            self.env["account.tax"]
            .with_context(lang="es_MX")
            .search(
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
        )
        invoice_lines = []
        for line in ecc12_node.Conceptos.ConceptoEstadoDeCuentaCombustible:
            taxes = []
            partner = self.search_partner_ecc12(line)
            vehicle = self.search_vehicle_ecc12(line)
            price = float(line.get("ValorUnitario", 0.0))
            if hasattr(line, "Traslados"):
                taxes = self.collect_taxes(line.Traslados.Traslado)
                if taxes:
                    # Split IEPS if is assigned in the XML
                    ieps = [tax for tax in taxes if tax.get("tax") == "IEPS"]
                    taxes = [tax for tax in taxes if tax.get("tax") != "IEPS"]
                    tax = taxes[0] if taxes else {}
                    tax_ids = []
                    tax_domain = self.prepare_tax_domain(
                        tax["name"], tax["amount"], tax["l10n_mx_factor_type"]
                    )
                    tax_exist = (
                        self.env["account.tax"]
                        .with_context(lang="es_MX")
                        .search(tax_domain, limit=1, order="id asc")
                    )
                    if tax_exist:
                        tax_ids.append(tax_exist.id)
                    price = round(tax.get("total") / (tax.get("amount") / 100), 2)
            invoice_lines.append(
                Command.create(
                    {
                        "name": _(
                            "Identifier: %s - Operation: %s - Station: %s",
                            line.get("Identificador"),
                            line.get("FolioOperacion"),
                            line.get("ClaveEstacion"),
                        ),
                        "vehicle_id": vehicle.id or False,
                        "quantity": float(line.get("Cantidad", 0.0)),
                        "price_unit": price / float(line.get("Cantidad", 0.0)),
                        "tax_ids": [Command.set(tax_ids)] if tax_ids else False,
                        "partner_id": partner.id,
                    },
                )
            )
            invoice_lines.append(
                Command.create(
                    {
                        "name": _("Fuel - IEPS"),
                        "vehicle_id": vehicle.id or False,
                        "quantity": 1.0,
                        "price_unit": (float(line.get("Importe", 0.0)) - price)
                        + float(ieps[0].get("amount", 0) if ieps else 0),
                        "tax_ids": [Command.set([tax_exempt.id])],
                        "partner_id": partner.id,
                    },
                )
            )
        return invoice_lines

    def prepare_invoice_lines(self, cfdi_etree, can_create_product=False):
        global_discount = cfdi_etree.get("Descuento", False)
        global_line_discount = 0
        if global_discount:
            global_line_discount = (
                float(cfdi_etree.get("Descuento"))
                * 100
                / float(cfdi_etree.get("SubTotal", 0.0))
            )
        invoice_lines = []
        for line in cfdi_etree.Conceptos.Concepto:
            # can_create_product = self._context.get("can_create_product", False)
            # account_id = self._context.get("account_id", False)
            uom_sat_exist = self.env["product.unspsc.code"].search(
                [
                    ("code", "=", line.get("ClaveUnidad", "")),
                    ("applies_to", "=", "uom"),
                ],
                limit=1,
            )
            uom_domain = [
                ("unspsc_code_id", "=", uom_sat_exist.id),
                ("name", "=ilike", line.get("Unidad", "")),
            ]
            uom_exist = (
                self.env["uom.uom"].with_context(lang="es_MX").search(uom_domain)
            )
            uom_exist = (
                uom_exist[0] if uom_exist else self.env.ref("uom.product_uom_unit")
            )

            line_name = line.get("Descripcion", "")
            if line_name.splitlines():
                line_name = line_name.splitlines()[0]
            product_exist = self.env["product.product"]
            supinfo_exist = self.env["product.supplierinfo"].search(
                [("product_name", "=ilike", line_name)], limit=1
            )
            if supinfo_exist:
                product_exist = product_exist.browse(supinfo_exist.product_tmpl_id.id)
            if not product_exist:
                product_exist = product_exist.search(
                    [
                        "|",
                        ("description_purchase", "=ilike", line_name),
                        ("name", "=ilike", line_name),
                    ],
                    limit=1,
                )
            if not product_exist and can_create_product:
                product_exist = product_exist.create(
                    {
                        "name": line_name,
                        "description_purchase": line_name,
                        "list_price": float(line.get("ValorUnitario")),
                        "type": "product",
                        "detailed_type": "product",
                        "uom_id": uom_exist.id,
                        "uom_po_id": uom_exist.id,
                        "l10n_mx_edi_code_sat_id": (
                            uom_sat_exist.id if uom_sat_exist else False
                        ),
                    }
                )

            line_discount = 0.0
            if global_line_discount:
                line_discount = global_line_discount
            elif line.get("Descuento"):
                line_discount = (
                    float(line.get("Descuento")) / float(line.get("Importe", "0.0"))
                ) * 100

            invoice_lines.append(
                Command.create(
                    {
                        "name": line_name,
                        "product_id": product_exist.id or False,
                        "quantity": float(line.get("Cantidad")),
                        "product_uom_id": (
                            product_exist.uom_id.id if product_exist else uom_exist.id
                        ),
                        "price_unit": float(line.get("ValorUnitario")),
                        "discount": line_discount,
                        "tax_ids": [Command.set(self.prepare_line_tax_ids(line))],
                    },
                )
            )

            # Case for fuel move line
            line_product_sat_code = line.get("ClaveProdServ", False)
            if line_product_sat_code in self.get_fuel_codes():
                tax = self.collect_taxes(line.Impuestos.Traslados.Traslado)
                fuel_line_price = tax[0].get("amount") / (tax[0].get("rate") / 100)
                invoice_lines.append(
                    Command.create(
                        {
                            "name": _("Fuel - IEPS"),
                            "quantity": 1,
                            "price_unit": float(line.get("Importe")) - fuel_line_price,
                            # "tax_ids": [Command.set(self.prepare_line_tax_ids(line))],
                        },
                    )
                )
        return invoice_lines

    def partner_search_create(self, cfdi_etree):
        partner_obj = self.env["res.partner"]
        import_type, move_type = self.get_import_type(cfdi_etree)
        domain_partner = []
        if import_type == "received":
            name = cfdi_etree.Emisor.get("Nombre", "")
            vat = cfdi_etree.Emisor.get("Rfc", "")
            domain_partner.append(("vat", "=", vat))
        elif import_type == "issued":
            name = cfdi_etree.Receptor.get("Nombre", "")
            vat = cfdi_etree.Receptor.get("Rfc", "")
            domain_partner.append(("vat", "=", vat))
        partner = partner_obj.search(domain_partner, limit=1, order="id asc")
        if not partner:
            vals = {
                "company_type": "company",
                "name": name,
                "vat": vat,
                "country_id": self.env.ref("base.mx").id,
            }
            partner = partner_obj.sudo().create(vals)
            msg = _(
                "This partner was created when importing a CFDI file. Please verify that Partner datas are correct."
            )
            partner.message_post(body=msg)
        return partner

    def prepare_move(self, cfdi_etree, journal=False):
        move_obj = self.env["account.move"]
        import_type, move_type = self.get_import_type(cfdi_etree)
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
            journal = self.env["account.journal"].search(
                domain, limit=1, order="id asc"
            )
        currency_exist = self.env["res.currency"].search(
            [("name", "=", self.get_currency(cfdi_etree))], limit=1
        )
        payment_form = self.env["l10n_mx_edi.payment.method"].search(
            [("code", "=", cfdi_etree.get("FormaDePago", cfdi_etree.get("FormaPago")))],
            limit=1,
        )
        payment_term = False
        if cfdi_etree.get("CondicionesDePago", False):
            payment_term = self.env["account.payment.term"].search(
                [("name", "=ilike", cfdi_etree.get("CondicionesDePago"))], limit=1
            )
        l10n_mx_edi_origin = False
        # related_uuids = {}
        # if hasattr(cfdi_etree, "CfdiRelacionados"):
        #     related_uuids = self.get_related_uuids_dict(cfdi_etree)
        # if cfdi_etree.get("TipoDeComprobante", False) == "E" and related_uuids:
        #     l10n_mx_edi_origin = move_obj._l10n_mx_edi_write_cfdi_origin(related_uuids["type"], related_uuids["uuids"])
        #     related_moves = move_obj.search([
        #        ("commercial_partner_id", "=", partner.id), ("move_type", "=", "in_invoice")])
        #     related_moves = related_moves.filtered(
        #        lambda inv: inv.l10n_mx_edi_cfdi_uuid in related_uuids["uuids"])
        #     TODO update core fields: reversed_entry_id, reversal_move_id
        #     related_moves.write({
        #        "refund_invoice_ids": [(4, invoice_id.id, 0)]
        #     })
        partner = self.partner_search_create(cfdi_etree)
        invoice_lines = []
        ecc12_node = self.collect_complemento(
            cfdi_etree,
            "//ecc12:EstadoDeCuentaCombustible",
            {"ecc12": "http://www.sat.gob.mx/EstadoDeCuentaCombustible12"},
        )
        local_taxes_node = self.collect_complemento(
            cfdi_etree,
            "implocal:ImpuestosLocales",
            {"implocal": "http://www.sat.gob.mx/implocal"},
        )
        if ecc12_node:
            ecc12_lines = self.prepare_invoice_lines_ecc12(ecc12_node)
            invoice_lines.extend(ecc12_lines)
        else:
            invoice_lines = self.prepare_invoice_lines(cfdi_etree)
            if local_taxes_node:
                local_taxes_lines = self.prepare_local_taxes(local_taxes_node)
                invoice_lines.extend(local_taxes_lines)
        vals = {
            "move_type": move_type,
            "journal_id": journal.id,
            "currency_id": currency_exist.id,
            "invoice_date": self.get_datetime(cfdi_etree),
            "invoice_payment_term_id": payment_term.id if payment_term else 1,
            "partner_id": partner.id,
            "name": (
                self.get_serie_folio(cfdi_etree) if import_type == "issued" else "/"
            ),
            "payment_reference": (
                self.get_serie_folio(cfdi_etree) if import_type == "received" else False
            ),
            "posted_before": bool(import_type == "issued"),
            "l10n_mx_edi_payment_method_id": (
                payment_form.id
                if payment_form
                else self.env.ref("l10n_mx_edi.payment_method_otros")
            ),
            "l10n_mx_edi_payment_policy": cfdi_etree.get("MetodoPago"),
            "l10n_mx_edi_usage": cfdi_etree.Receptor.get("UsoCFDI", "S01"),
            "l10n_mx_edi_post_time": self.get_datetime(cfdi_etree),
            "l10n_mx_edi_cfdi_origin": l10n_mx_edi_origin,
            "x_check_tax": (
                float(cfdi_etree.Impuestos.get("TotalImpuestosTrasladados", 0.0))
                if hasattr(cfdi_etree, "Impuestos")
                else 0.0
            ),
            "x_check_total": float(cfdi_etree.get("Total", 0.0)),
            "invoice_line_ids": invoice_lines,
        }
        return vals

    def prepare_cfdi_dupli_domain(self, cfdi_etree):
        import_type, move_type = self.get_import_type(cfdi_etree)
        domain = [
            ("move_type", "=", move_type),
            ("invoice_date", "=", self.get_datetime(cfdi_etree)),
            # TODO l10n_mx_edi does wrong this part
            # ("l10n_mx_edi_post_time", "=", cfdi_dict["datetime"])
        ]
        if import_type == "received":
            domain.append(("payment_reference", "=", self.get_serie_folio(cfdi_etree)))
        elif import_type == "issued":
            domain.append(("name", "=", self.get_serie_folio(cfdi_etree)))
        partner = self.partner_search_create(cfdi_etree)
        l10n_mx_edi_cfdi_uuid = self.collect_complemento(cfdi_etree).get("UUID").upper()
        domain.extend(
            [
                ("commercial_partner_id", "=", partner.id),
                ("l10n_mx_edi_cfdi_uuid", "=", l10n_mx_edi_cfdi_uuid),
            ]
        )
        return domain

    def check_cfdi_dupli(self, cfdi_etree):
        domain = self.prepare_cfdi_dupli_domain(cfdi_etree)
        fuzzy_domain = domain[:-1]
        exact_move_exist = self.env["account.move"].search(domain)
        # FIX-ME: improve fuzzy domain because it attachs more than 1 document in the account move
        fuzzy_move_exist = self.env["account.move"].search(fuzzy_domain)
        if (
            exact_move_exist
            and len(fuzzy_move_exist) >= 1
            or not exact_move_exist
            and len(fuzzy_move_exist) > 1
        ):
            raise ValidationError(_("Duplicated: "))
        if (
            not exact_move_exist
            and len(fuzzy_move_exist) == 1
            and not fuzzy_move_exist.l10n_mx_edi_cfdi_uuid
        ):
            exact_move_exist = fuzzy_move_exist
        return exact_move_exist

    def xml2record(self, cfdi_etree, journal=False):
        validation = self.check_cfdi_dupli(cfdi_etree)
        if not validation:
            vals = self.prepare_move(cfdi_etree, journal)
            validation = (
                self.env["account.move"]
                .with_context(default_move_type=vals["move_type"])
                .create(vals)
            )
        return validation

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
                            element_receptor = element_root.find(
                                ".//des:RfcReceptor", internal_nsmap
                            )
                            element_receptor.text = rfc_receptor
                    continue

                if arguments[key] is not None:
                    element.set(key, arguments[key])

        digest_value = element_signature.find(".//DigestValue", internal_nsmap)
        digest_value.text = base64.b64encode(
            hashlib.sha1(
                etree.tostring(element_to_digest, method="c14n", exclusive=1)
            ).digest()
        )
        element_to_sign = element_signature.find(".//SignedInfo", internal_nsmap)
        element_to_sign = etree.tostring(element_to_sign, method="c14n", exclusive=1)
        element_signed = element_signature.find(".//SignatureValue", internal_nsmap)
        element_signed.text = (
            base64.b64encode(crypto.sign(private_key, element_to_sign, "sha1"))
            .decode("UTF-8")
            .replace("\n", "")
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
            element_certificate = element_root.find(
                ".//o:BinarySecurityToken", internal_nsmap
            )
            element_certificate.text = base64.b64encode(
                crypto.dump_certificate(crypto.FILETYPE_ASN1, certificate)
            )
        else:
            element_certificate = element_key_info.find(".//X509Certificate")
            element_certificate.text = base64.b64encode(
                crypto.dump_certificate(crypto.FILETYPE_ASN1, certificate)
            )
            cer_issuer = certificate.get_issuer().get_components()
            cer_issuer = ",".join(
                [
                    "{key}={value}".format(key=key.decode(), value=value.decode())
                    for key, value in cer_issuer
                ]
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
        communication = self.check_comm(
            url, data, headers, result_xpath, external_nsmap
        )
        ret_dict = {
            "status": communication.find("a:Estado", external_nsmap).text,
            "is_cancellable": communication.find("a:EsCancelable", external_nsmap).text,
            "cancel_status": communication.find(
                "a:EstatusCancelacion", external_nsmap
            ).text,
            "efos_validation": communication.find(
                "a:ValidacionEFOS", external_nsmap
            ).text,
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
        data = self.prepare_soap_data(
            certificate, private_key, {"uuid": f"uuid-{uuid}-4"}, envelop, xpath, False
        )
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
        communication = self.check_comm(
            url, data, headers, result_xpath, external_nsmap
        )
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
            raise ValidationError(_("Validation error"))

        holder_vat = "".join(
            certificate.get_subject().x500UniqueIdentifier.split(" ")[0]
        )
        sanitized = self.sanitize_args(args)
        arguments = {
            "UUID": sanitized["uuid"] if "uuid" in sanitized else None,
            "RfcSolicitante": holder_vat,
            "RfcEmisor": (
                sanitized["emitter_vat"]
                if "emitter_vat" in sanitized and "uuid" not in sanitized
                else None
            ),
            "RfcReceptores": (
                sanitized["receiver_vats"]
                if "receiver_vats" in sanitized and "uuid" not in sanitized
                else [holder_vat]
            ),
            "FechaInicial": (
                sanitized["date_from"].isoformat() if "date_from" in sanitized else None
            ),
            "FechaFinal": (
                sanitized["date_to"].isoformat() if "date_to" in sanitized else None
            ),
            "TipoSolicitud": (
                sanitized["request_type"] if "request_type" in sanitized else "CFDI"
            ),
            "TipoComprobante": (
                sanitized["cfdi_type"]
                if "cfdi_type" in sanitized and "uuid" not in sanitized
                else None
            ),
            "EstadoComprobante": (
                sanitized["cfdi_state"]
                if "cfdi_state" in sanitized and "uuid" not in sanitized
                else None
            ),
            "RfcACuentaTerceros": (
                sanitized["thirthparty_vat"]
                if "thirthparty_vat" in sanitized and "uuid" not in sanitized
                else None
            ),
            "Complemento": (
                sanitized["complement"]
                if "complement" in sanitized and "uuid" not in sanitized
                else None
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
        data = self.prepare_soap_data(
            certificate, private_key, arguments, envelop, xpath, token
        )
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
        communication = self.check_comm(
            url, data, headers, result_xpath, external_nsmap
        )
        ret_dict = {
            "id_solicitud": communication.get("IdSolicitud"),
            "cod_estatus": communication.get("CodEstatus"),
            "mensaje": communication.get("Mensaje"),
        }
        return ret_dict

    def l10n_mx_ws_verify_package(self, certificate, private_key, token, id_solicitud):
        arguments = {
            "RfcSolicitante": certificate.get_subject().x500UniqueIdentifier.split(" ")[
                0
            ],
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
        data = self.prepare_soap_data(
            certificate, private_key, arguments, envelop, xpath, token
        )
        url = "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/VerificaSolicitudDescargaService.svc"
        soap_action = "http://DescargaMasivaTerceros.sat.gob.mx/IVerificaSolicitudDescargaService/VerificaSolicitudDescarga"
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
        result_xpath = (
            "s:Body/VerificaSolicitudDescargaResponse/VerificaSolicitudDescargaResult"
        )
        communication = self.check_comm(
            url, data, headers, result_xpath, external_nsmap
        )
        ret_dict = {
            "cod_estatus": communication.get("CodEstatus"),
            "estado_solicitud": communication.get("EstadoSolicitud"),
            "codigo_estado_solicitud": communication.get("CodigoEstadoSolicitud"),
            "numero_cfdis": communication.get("NumeroCFDIs"),
            "mensaje": communication.get("Mensaje"),
            "paquetes": [],
        }
        for id_paquete in communication.iter(
            "{{{}}}IdsPaquetes".format(external_nsmap[""])
        ):
            ret_dict["paquetes"].append(id_paquete.text)
        return ret_dict

    def l10n_mx_ws_download_package(self, certificate, private_key, token, id_paquete):
        arguments = {
            "RfcSolicitante": certificate.get_subject().x500UniqueIdentifier.split(" ")[
                0
            ],
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
        data = self.prepare_soap_data(
            certificate, private_key, arguments, envelop, xpath, token
        )
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
        communication = self.check_comm(
            url, data, headers, result_xpath, external_nsmap
        )
        respuesta = (
            communication.getparent()
            .getparent()
            .getparent()
            .find("s:Header/h:respuesta", namespaces=external_nsmap)
        )
        ret_dict = {
            "cod_estatus": respuesta.get("CodEstatus"),
            "mensaje": respuesta.get("Mensaje"),
            "paquete_b64": communication.text,
        }
        return ret_dict

    def _l10n_mx_edi_is_cfdi(self, xml64):
        is_cfdi = False
        try:
            cfdi_etree = self.env["l10n_mx_edi.document"].check_objectify_xml(xml64)
            is_cfdi = cfdi_etree.tag in [
                "{http://www.sat.gob.mx/cfd/3}Comprobante",
                "{http://www.sat.gob.mx/cfd/4}Comprobante",
            ]
        except Exception:
            pass
        return is_cfdi

    def is_payment_complement(self, cfdi_etree):
        """
        Uses the provided collect_complemento function to detect if the CFDI
        includes a payment complement (Pagos 1.0 or 2.0).

        Args:
            cfdi_etree (etree.Element): Parsed CFDI XML tree.
            collect_complemento_func (callable): A function that extracts nodes from CFDI Complemento.

        Returns:
            bool: True if it is a payment complement, False otherwise.
        """
        namespaces = {
            "pago10": "http://www.sat.gob.mx/Pagos10",
            "pago20": "http://www.sat.gob.mx/Pagos20",
        }

        # Try with version 2.0
        pago_node_20 = self.collect_complemento(
            cfdi_etree,
            attribute="pago20:Pagos",
            namespaces=namespaces,
        )

        if pago_node_20 is not None:
            return True

        # Try with version 1.0 if 2.0 not found
        pago_node_10 = self.collect_complemento(
            cfdi_etree,
            attribute="pago10:Pagos",
            namespaces=namespaces,
        )
        return bool(pago_node_10)
