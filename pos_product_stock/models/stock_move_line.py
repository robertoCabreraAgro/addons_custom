from odoo import api, models


class StockMoveLine(models.Model):
    """Inherits model "stock.move.line to load pos data fields"""

    _name = "stock.move.line"
    _inherit = ["stock.move.line", "pos.load.mixin"]

    @api.model
    def _load_pos_data_fields(self, config_id):
        """Returns the list of fields to be loaded for POS data."""
        result = super()._load_pos_data_fields(config_id)
        result.append("product_id")
        result.append("location_dest_id")
        result.append("quantity")
        result.append("location_id")
        return result
