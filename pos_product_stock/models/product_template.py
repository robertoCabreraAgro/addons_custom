from odoo import api, fields, models


class ProductTemplate(models.Model):
    """inherit product.template to load field in pos."""

    _inherit = ["product.template", "pos.load.mixin"]

    deny = fields.Integer(
        string="Deny POS Order",
        default=0,
        help="Set a limit so that you can deny POS Order",
    )

    @api.model
    def _load_pos_data_fields(self, config_id):
        """Returns the fields to be loaded for POS data."""
        result = super()._load_pos_data_fields(config_id)
        result.append("qty_available")
        result.append("incoming_qty")
        result.append("outgoing_qty")
        result.append("deny")
        return result
