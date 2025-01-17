from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockQuantLotUpdate(models.TransientModel):
    _name = "stock.quant.lot.update"
    _description = "Change Quant Lot Wizard"


    quant_id = fields.Many2one(
        comodel_name="stock.quant",
        required=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        related="quant_id.product_id",
        required=True,
        readonly=True,
    )
    lot_id = fields.Many2one(
        related="quant_id.lot_id",
        readonly=True,
    )
    dest_lot_id = fields.Many2one(
        comodel_name="stock.lot",
        required=True,
        domain="[('product_id', '=', product_id), ('id', '!=', lot_id)]",
        string="Destination Lot",
    )
    max_quantity = fields.Float(related="quant_id.quantity")
    quantity = fields.Float(
        required=True,
        help="Quantity to be transfered to the destintation lot.",
    )


    @api.model
    def default_get(self, list_fields):
        res = super().default_get(list_fields)
        if self._context.get("active_model") == "stock.quant":
            quant = self.env["stock.quant"].browse(self._context.get("active_ids", []))[:1]
            res.update(
                {
                    "quant_id": quant.id,
                    "quantity": quant.quantity,
                }
            )
        return res

    @api.onchange(quantity)
    def _onchange_transfer_quantity(self):
        qty = min(self.quantity, self.max_quantity)
        self.quantity = max(qty, 0.0)

    def action_apply_inventory(self):
        quant_obj = self.env["stock.quant"]
        quant = self.quant_id
        dest_quant = quant_obj.search(
            [
                ("lot_id", "=", self.dest_lot_id.id),
                ("product_id", "=", self.product_id.id),
                ("location_id", "=", quant.location_id.id),
            ]
        )
        if dest_quant:
            raise UserError(_(
                "You are trying to move the location of a product. Use an Internal "
                "Transfer instead."
            ))
        self._cr.execute(
            f"UPDATE stock_quant SET lot_id={self.dest_lot_id.id} WHERE id={quant.id}"
        )
