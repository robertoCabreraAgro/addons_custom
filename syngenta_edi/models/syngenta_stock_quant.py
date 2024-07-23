from odoo import fields, models


class SyngentaStockReportLine(models.Model):
    _name = "syngenta.stock.report.line"
    _order = "sequence, id"
    _description = "Inventory report line send to Syngenta"

    company_id = fields.Many2one("res.company", index=True, required=True, default=lambda self: self.env.company.id)
    product_id = fields.Many2one(
        "product.product",
        "Product",
        required=True,
        # domain=lambda self: [("manufacturer_id", "=", self.env.ref("syngenta_edi.partner_syngenta", False).id)],
    )
    product_category_id = fields.Many2one(related="product_id.categ_id", store=True)
    quantity = fields.Float(digits="Product Unit of Measure")
    transit_quantity = fields.Float(digits="Product Unit of Measure")
    date_inventory = fields.Date("Inventory Date")
    sequence = fields.Integer(default=10)

    def _get_json_lines(self):
        lines = []
        for rec in self:
            lines.append(rec._get_json_line())
        return lines

    def _get_json_line(self):
        self.ensure_one()
        inventory_date = (self.date_inventory or self.env.context.get("inventory_date")).strftime("%Y-%m-%d") or ""
        return {
            "fecha_Inventario": inventory_date,  # YYYY-MM-DD
            "linea_Negocio": "",  # Not required
            "codeProduct_Distribuidor": self.product_id.manufacturer_pref or "",
            "presentacion": "",  # Not required
            "unidad_Medida": "",  # Not required
            "volumen_Inventario": self.quantity or 0.0,
            "almacen": "",  # Not required
            "municipio": "",  # Not required
            "no_ShipTo": "",  # Not required
            "pais": "Mexico",  # Not required
            "inventario_EnTransito": self.transit_quantity or 0.0,  # Not required
        }
