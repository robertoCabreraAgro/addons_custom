from odoo import api, fields, models


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    production_type = fields.Selection(
        related="bom_id.production_type",
        store=True,
        readonly=True,
    )

    @api.onchange(
        "product_id", "move_raw_ids", "never_product_template_attribute_value_ids"
    )
    def _onchange_product_id(self):
        if self.bom_id and self.bom_id.production_type == "reformulated":
            return
        super()._onchange_product_id()
