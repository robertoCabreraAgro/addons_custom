from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    manufacturer_id = fields.Many2one(comodel_name="res.partner", string="Manufacturer")
    manufacturer_pname = fields.Char(string="Manuf. Product Name")
    manufacturer_pref = fields.Char(string="Manuf. Product Code")
    manufacturer_purl = fields.Char(string="Manuf. Product URL")
