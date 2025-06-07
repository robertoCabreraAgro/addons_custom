from odoo import api, models


class StockLocation(models.Model):
    """Inherits model "stock.location to load pos data fields"""

    _name = "stock.location"
    _inherit = ["stock.location", "pos.load.mixin"]

    @api.model
    def _load_pos_data_fields(self, config_id):
        """Returns the list of fields to be loaded for POS data."""
        result = super()._load_pos_data_fields(config_id)
        result.append("child_ids")
        return result
