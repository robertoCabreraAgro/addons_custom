from odoo import api, fields, models


class SyngentaSaleLine(models.Model):
    _name = "syngenta.sale.line"
    _order = "agreement_id, document_id, sequence, id"
    _description = "Report line send to Syngenta with customer's consumptions"

    name = fields.Char("Name")
    company_id = fields.Many2one(
        "res.company",
        index=True,
        required=True,
        default=lambda self: self.env.company.id,
        readonly=True,
    )
    document_id = fields.Many2one(
        "syngenta.sale.document",
        "Document",
    )
    agreement_id = fields.Many2one(related="document_id.agreement_id")
    partner_id = fields.Many2one(related="agreement_id.partner_id")
    product_id = fields.Many2one(
        "product.product",
        "Product",
        required=True,
        domain=lambda self: [("manufacturer_id", "=", self.env.ref("syngenta_edi.partner_syngenta", False).id)],
    )
    product_qty = fields.Float(
        string="Quantity",
        digits="Product Unit of Measure",
        required=True,
    )
    price_unit = fields.Float(
        string="Unit Price",
        digits="Product Price",
        required=True,
        compute="_compute_price_unit_and_date_planned_and_name",
        store=True,
        readonly=False,
    )
    price_subtotal = fields.Float(
        string="Subtotal",
        digits=(16, 2),
        compute="_compute_amounts",
        store=True,
        readonly=False,
        help="Amount asigned to the sale agreement that will be " "used as base for following calculations.",
    )
    is_sent = fields.Boolean("Sent to Syngenta", compute="_compute_is_sent", store=True)
    sequence = fields.Integer(default=10)

    @api.depends("product_qty", "price_unit")
    def _compute_amounts(self):
        for line in self:
            line.update(
                {
                    "price_subtotal": line.product_qty * line.price_unit,
                }
            )

    @api.depends("document_id.state")
    def _compute_is_sent(self):
        for line in self:
            line.is_sent = self.document_id.state == "done"

    def _get_json_lines(self):
        lines = []
        for rec in self:
            lines.append(rec._get_json_line())
        if lines:
            lines[0].update(
                {
                    "rfc": self[0].document_id.partner_id.vat or "",
                    "numero_Convenio": self[0].agreement_id.number or "",
                }
            )
        return lines

    def _get_json_line(self):
        self.ensure_one()
        return {
            "folio": self.document_id.folio or "",
            "fecha_Facturacion": self.document_id.date.strftime("%Y-%m-%d") or "",  # YYYY-MM-DD
            "volumen_Facturado": self.product_qty or 0.0,
            "unidad_Medida": "",  # Not required
            "valorT_Facturado": self.price_subtotal or 0.0,
            "nombre_Cliente": self.partner_id.name or "",
            "nombre_Vendedor_Distribuidor": "",  # Not required
            "codeProduct_Distribuidor": self.product_id.manufacturer_pref or "",
            "localidad": "",  # Not required
            "sucursal": "",  # Not required
            "linea_Producto": "",  # Not required
            "marca": "SYNGENTA",  # Not required
            "pais": "Mexico",  # Not required
            "rfc": "",  # Not required
            "numero_Convenio": "",  # Not required
        }
