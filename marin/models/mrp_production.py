from odoo import api, models
import logging

_logger = logging.getLogger(__name__)

class MrpProduction(models.Model):
    _inherit = "mrp.production"

    @api.onchange('product_id', 'move_raw_ids', 'never_product_template_attribute_value_ids')
    def _onchange_product_id(self):
        """
        Inherits the original validation and skips the restriction when `x_type == "reformulate"`.
        """
        if self.bom_id and self.bom_id.x_type == "reformulate":
            _logger.info("Skipping _onchange_product_id validation for reformulate BOM: %s", self.product_id.display_name)
            return          
        else:
            super()._onchange_product_id()

    #TODO reviw this code with Luis
    # def _set_qty_producing(self):
    #     return super(MrpProduction, self.with_context(mrp_production=True))._set_qty_producing()
