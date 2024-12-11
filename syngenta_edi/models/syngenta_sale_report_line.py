from odoo import api, fields, models
from odoo.tools.float_utils import float_round


class SyngentaSaleReportLine(models.Model):
    _name = "syngenta.sale.report.line"
    _order = "agreement_id, report_id, sequence, id"
    _description = "Report line send to Syngenta with customer's consumptions"


    name = fields.Char("Name")
    report_id = fields.Many2one(
        "syngenta.sale.report",
        "Document",
    )
    company_id = fields.Many2one(
        related='report_id.company_id',
        store=True, 
        readonly=True,
    )
    agreement_id = fields.Many2one(related="report_id.agreement_id")
    partner_id = fields.Many2one(related="agreement_id.partner_id")
    product_id = fields.Many2one(
        "product.product",
        "Product",
        required=True,
        domain=[("manufacturer_id.name", "ilike", "syngenta")],
    )
    product_qty = fields.Float(
        "Quantity",
        "Product Unit of Measure",
        required=True,
    )
    price_unit = fields.Float(
        "Unit Price",
        "Product Price",
        required=True,
        # compute="_compute_price_unit", store=True,
        readonly=False,
    )
    price_subtotal = fields.Float(
        string="Subtotal",
        digits=(16, 2),
        compute="_compute_amounts", store=True,
        readonly=False,
        help="Amount asigned to the sale agreement that will "
             "be used as base for following calculations.",
    )
    is_sent = fields.Boolean("Sent to Syngenta", compute="_compute_is_sent", store=True)
    sequence = fields.Integer(default=10)


    @api.depends('company_id', 'product_qty',  'report_id.partner_id')
    def _compute_price_unit(self):
        for line in self:
            if not line.company_id or not line.product_id:
                continue

            seller = line.product_id._select_seller(
                partner_id=line.partner_id,
                quantity=line.product_qty,
                date=fields.Date.context_today(line),
                uom_id=line.product_id.uom_po_id,
            )

            if not seller:
                unavailable_seller = line.product_id.seller_ids.filtered(
                    lambda s: s.partner_id == line.report_id.partner_id
                )
                if not unavailable_seller and line.price_unit:
                    # Avoid to modify the price unit if there is no price list for this partner and
                    # the line has already one to avoid to override unit price set manually.
                    continue

                po_line_uom = line.product_id.uom_po_id
                price_unit = line.product_id.uom_id._compute_price(
                        line.product_id.standard_price, po_line_uom
                )
                price_unit = line.product_id.cost_currency_id._convert(
                    price_unit,
                    line.company_id.currency_id,
                    line.company_id,
                    fields.Date.context_today(line),
                    False
                )
                line.price_unit = float_round(
                    price_unit,
                    precision_digits=max(
                        line.currency_id.decimal_places,
                        self.env['decimal.precision'].precision_get('Product Price')
                    )
                )

            elif seller:
                price_unit = line.env['account.tax']._fix_tax_included_price_company(
                    seller.price,
                    line.product_id.supplier_taxes_id,
                    (),
                    line.company_id
                )
                price_unit = seller.currency_id._convert(
                    price_unit,
                    line.currency_id,
                    line.company_id,
                    fields.Date.context_today(line),
                    False
                )
                price_unit = float_round(
                    price_unit,
                    precision_digits=max(
                        line.currency_id.decimal_places,
                        self.env['decimal.precision'].precision_get('Product Price')
                    )
                )

    @api.depends("product_qty", "price_unit")
    def _compute_amounts(self):
        for line in self:
            line.update(
                {"price_subtotal": line.product_qty * line.price_unit}
            )

    @api.depends("report_id.state")
    def _compute_is_sent(self):
        for line in self:
            line.is_sent = self.report_id.state == "done"

    def _get_json_line(self):
        self.ensure_one()
        return {
            "folio": self.report_id.folio or "",
            "fecha_Facturacion": self.report_id.date.strftime("%Y-%m-%d") or "",  # YYYY-MM-DD
            "volumen_Facturado": self.product_qty or 0.0,
            "unidad_Medida": "",  # Not required
            "valorT_Facturado": self.price_subtotal or 0.0,
            "nombre_Cliente": self.partner_id.name or "",
            "nombre_Vendedor_Distribuidor": "",  # Not required
            "codeProduct_Distribuidor": self.product_id.manufacturer_pref or "",
            "nombreProduct_Distribuidor": self.product_id.name or "",
            "localidad": "",  # Not required
            "sucursal": "",  # Not required
            "linea_Producto": "",  # Not required
            "marca": "SYNGENTA",  # Not required
            "pais": "Mexico",  # Not required
            "rfc": "",  # Not required
            "numero_Convenio": "",  # Not required
        }
