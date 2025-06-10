from odoo import api, fields, models


class PosConfig(models.Model):
    """inherit pos.config to add fields."""

    _inherit = "pos.config"

    pos_stock_location_id = fields.Many2one(
        "stock.location",
        string="Stock Location",
        help="This field helps to hold the location",
    )
    location_from = fields.Selection(
        [("all_warehouse", "All Location"), ("current_warehouse", "Current Location")],
        string="Show Stock Of",
        help="can choose the location where you want to display the stock ",
    )
    display_stock_setting = fields.Boolean(
        string="Display Stock",
        help="By enabling you can view quantity in Point Of Sale",
        default=False,
    )
    stock_product = fields.Selection(
        [
            ("on_hand", "On Hand Quantity"),
            ("incoming_qty", "Incoming Quantity"),
            ("outgoing_qty", "Outgoing Quantity"),
        ],
        string="Stock Type",
        help="Help you to choose the quantity you want to visible in pos",
    )

    @api.onchange("location_from")
    def _onchange_location_from(self):
        """Adjust the stock_location_id when stock_from is changed."""
        if self.location_from == "all_warehouse":
            self.stock_location_id = False
        elif self.location_from == "current_warehouse":
            self.stock_location_id = self.pos_config_id.pos_stock_location_id
