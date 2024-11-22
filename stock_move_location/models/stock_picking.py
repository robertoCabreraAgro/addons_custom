from odoo import _, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"


    def _validate_picking(self):
        if self.location_id.child_ids:
            raise UserError(_("Please choose a source end location"))
        if self.move_ids:
            raise UserError(_("Moves lines already exists"))

    def _get_movable_quants(self):
        return (
            self.env["stock.quant"]
            .search(
                [
                    ("location_id", "=", self.location_id.id),
                    ("quantity", ">", 0.0),
                ]
            )
            .filtered(lambda quant: quant.quantity - quant.reserved_quantity > 0.0)
        )

    def button_fillwithstock(self):
        # check source location has no children, i.e. we scanned a bin
        self.ensure_one()
        self._validate_picking()
        context = {
            "active_ids": self._get_movable_quants().ids,
            "active_model": "stock.quant",
            "only_reserved_qty": True,
            "planned": True,
        }
        move_wizard = (
            self.env["stock.quant.relocate"]
            .with_context(**context)
            .create({
                "location_destination_id": self.location_dest_id.id,
                "location_origin_id": self.location_id.id,
                "picking_type_id": self.picking_type_id.id,
                "picking_id": self.id,
            })
        )
        move_wizard._onchange_location_destination_id()
        move_wizard.action_move_location()
        return True
