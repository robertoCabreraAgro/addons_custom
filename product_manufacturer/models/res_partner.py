from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    manufacturer = fields.Boolean()
    product_ids = fields.One2many(
        "product.template",
        "manufacturer_id",
    )
    product_count = fields.Integer(
        compute="_compute_product_count",
    )

    @api.depends("product_ids")
    def _compute_product_count(self):
        model_data = self.env["product.template"]._read_group(
            [("manufacturer_id", "in", self.ids)],
            ["manufacturer_id"],
            ["__count"],
        )
        models_brand = {brand.id: count for brand, count in model_data}
        for record in self:
            record.product_count = models_brand.get(record.id, 0)

    def action_brand_model(self):
        self.ensure_one()
        view = {
            "name": "Models",
            "type": "ir.actions.act_window",
            "res_model": "product.template",
            "view_mode": "list,form",
            "context": {
                "search_default_manufacturer_id": self.id,
                "default_manufacturer_id": self.id,
            },
        }
        return view
