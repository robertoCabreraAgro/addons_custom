from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare
import logging

_logger = logging.getLogger(__name__)


class StockQuantRelocateLine(models.TransientModel):
    _name = "stock.quant.relocate.line"
    _description = "Wizard move location line"

    move_location_wizard_id = fields.Many2one(
        comodel_name="stock.quant.relocate",
        string="Move location Wizard",
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product",
        required=True,
    )
    location_origin_id = fields.Many2one(
        comodel_name="stock.location",
        string="Origin Location",
    )
    location_destination_id = fields.Many2one(
        comodel_name="stock.location",
        string="Destination Location",
    )
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Product Unit of Measure",
    )
    package_id = fields.Many2one(
        comodel_name="stock.quant.package",
        string="Package Number",
        domain="[('location_id', '=', location_origin_id)]",
    )
    lot_id = fields.Many2one(
        comodel_name="stock.lot",
        string="Lot/Serial Number",
        domain="[('product_id','=',product_id)]",
    )
    owner_id = fields.Many2one(
        comodel_name="res.partner",
        string="From Owner",
    )
    move_quantity = fields.Float(
        string="Quantity to move", digits="Product Unit of Measure"
    )
    max_quantity = fields.Float(
        string="Maximum available quantity", digits="Product Unit of Measure"
    )
    total_quantity = fields.Float(
        string="Total existence quantity", digits="Product Unit of Measure"
    )
    reserved_quantity = fields.Float(digits="Product Unit of Measure")
    custom = fields.Boolean(string="Custom line", default=True)

    @api.constrains("max_quantity", "move_quantity")
    def _constraint_max_move_quantity(self):
        for record in self:

            rounding = record.product_uom_id.rounding or 1
            if rounding < 1:
                _logger.warning(
                    "Rounding value '%s' adjusted to 1 for float_compare compatibility",
                    rounding,
                )
                rounding = 1
            move_qty_gt_max_qty = (
                float_compare(record.move_quantity, record.max_quantity, rounding) == 1
            )
            move_qty_lt_0 = float_compare(record.move_quantity, 0.0, rounding) == -1
            if move_qty_gt_max_qty or move_qty_lt_0:
                raise ValidationError(
                    _("Move quantity can not exceed max quantity or be negative")
                )

    def _get_available_quantity(self):
        """
        We check here if the actual amount changed in the stock.
        We don't care about the reservations but we do care about not moving
        more than exists.
        """
        self.ensure_one()
        if not self.product_id:
            return 0
        if self.env.context.get("planned"):
            # for planned transfer we don't care about the amounts at all
            return 0.0
        search_args = [
            ("location_id", "=", self.location_origin_id.id),
            ("product_id", "=", self.product_id.id),
        ]
        if self.lot_id:
            search_args.append(("lot_id", "=", self.lot_id.id))
        else:
            search_args.append(("lot_id", "=", False))
        if self.package_id:
            search_args.append(("package_id", "=", self.package_id.id))
        else:
            search_args.append(("package_id", "=", False))
        if self.owner_id:
            search_args.append(("owner_id", "=", self.owner_id.id))
        else:
            search_args.append(("owner_id", "=", False))
        res = self.env["stock.quant"].read_group(search_args, ["quantity"], [])
        available_qty = res[0]["quantity"]
        if not available_qty:
            # if it is immediate transfer and product doesn't exist in that
            # location -> make the transfer of 0.
            return 0

        rounding = self.product_uom_id.rounding
        available_qty_lt_move_qty = (
            float_compare(available_qty, self.move_quantity, rounding) == -1
        )
        return available_qty if available_qty_lt_move_qty else self.move_quantity

    def _get_move_line_values(self, picking, move):
        self.ensure_one()
        location_dest_id = (
            self.move_location_wizard_id.apply_putaway_strategy
            and self.location_destination_id._get_putaway_strategy(self.product_id).id
            or self.location_destination_id.id
        )
        qty_done = self._get_available_quantity()
        move_values = {
            "product_id": self.product_id.id,
            "lot_id": self.lot_id.id,
            "package_id": self.package_id.id,
            "result_package_id": self.package_id.id,
            "owner_id": self.owner_id.id,
            "location_id": self.location_origin_id.id,
            "location_dest_id": location_dest_id,
            "quantity": qty_done,
            "product_uom_id": self.product_uom_id.id,
            "move_id": move.id,
        }
        if picking:
            move_values["picking_id"] = picking.id
        return move_values

    def create_move_lines(self, picking, move):
        for line in self:
            values = line._get_move_line_values(picking, move)
            if not self.env.context.get("planned") and values.get("quantity") <= 0:
                continue
            self.env["stock.move.line"].create(values)
        return True
