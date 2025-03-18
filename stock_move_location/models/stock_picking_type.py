from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    show_move_onhand = fields.Boolean(
        string="Show Move On hand stock",
        help="Show a button 'Move On Hand' in the Inventory Dashboard "
        "to initiate the process to move the products in stock "
        "at the origin location.",
    )

    def action_move_location(self):
        action = self.env.ref("stock_move_location.stock_quant_relocate_action").read()[
            0
        ]
        action["context"] = {
            "default_location_origin_id": self.default_location_src_id.id,
            "default_location_destination_id": self.default_location_dest_id.id,
            "default_picking_type_id": self.id,
            "default_edit_locations": False,
        }
        return action
