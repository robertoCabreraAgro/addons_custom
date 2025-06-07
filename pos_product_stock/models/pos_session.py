from odoo import api, models


class PosSession(models.Model):
    """inherit pos.session to add fields and modules in session."""

    _inherit = "pos.session"

    @api.model
    def _load_pos_data_models(self, config_id):
        """The list of models to be loaded for POS data."""
        data = super()._load_pos_data_models(config_id)
        data += ["stock.location", "stock.quant", "stock.move.line"]
        return data
