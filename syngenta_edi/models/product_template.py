from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    manufacturer_id = fields.Many2one(
        "res.partner",
        "Manufacturer",
        compute="_compute_manufacturer_info",
        inverse="_inverse_manufacturer_info",
        store=True,
    )
    manufacturer_pname = fields.Char(
        "Manuf. Product Name", compute="_compute_manufacturer_info", inverse="_inverse_manufacturer_info", store=True
    )
    manufacturer_pref = fields.Char(
        "Manuf. Product Code", compute="_compute_manufacturer_info", inverse="_inverse_manufacturer_info", store=True
    )
    manufacturer_purl = fields.Char(
        "Manuf. Product URL", compute="_compute_manufacturer_info", inverse="_inverse_manufacturer_info", store=True
    )

    @api.depends(
        "product_variant_ids",
        "product_variant_ids.manufacturer_id",
        "product_variant_ids.manufacturer_pname",
        "product_variant_ids.manufacturer_pref",
        "product_variant_ids.manufacturer_purl",
    )
    def _compute_manufacturer_info(self):
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for template in unique_variants:
            template.manufacturer_id = template.product_variant_ids.manufacturer_id
            template.manufacturer_pname = template.product_variant_ids.manufacturer_pname
            template.manufacturer_pref = template.product_variant_ids.manufacturer_pref
            template.manufacturer_purl = template.product_variant_ids.manufacturer_purl
        for template in self - unique_variants:
            template.manufacturer_id = False
            template.manufacturer_pname = False
            template.manufacturer_pref = False
            template.manufacturer_purl = False

    def _inverse_manufacturer_info(self):
        for template in self:
            if len(template.product_variant_ids) == 1:
                template.product_variant_ids.manufacturer_id = template.manufacturer_id
                template.product_variant_ids.manufacturer_pname = template.manufacturer_pname
                template.product_variant_ids.manufacturer_pref = template.manufacturer_pref
                template.product_variant_ids.manufacturer_purl = template.manufacturer_purl
