from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    manufacturer_id = fields.Many2one(comodel_name="res.partner")
    manufacturer_pname = fields.Char(string="Manufacturer Product Name")
    manufacturer_pref = fields.Char(string="Manufacturer Product Code")
    manufacturer_purl = fields.Char(string="Manufacturer Product URL")
