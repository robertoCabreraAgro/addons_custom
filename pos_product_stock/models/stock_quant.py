from odoo import api, models


class StockQuant(models.Model):
    """Inherits model "stock.quant to load pos data"""

    _name = "stock.quant"
    _inherit = ["stock.quant", "pos.load.mixin"]

    @api.model
    def _load_pos_data_fields(self, config_id):
        """Returns the list of fields to be loaded for POS data."""
        return ["product_id", "available_quantity", "quantity", "location_id"]
