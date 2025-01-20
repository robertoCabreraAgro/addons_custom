from odoo import api, fields, models


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
        string="Destination Lot",
        required=True,
        domain="[('product_id', '=', product_id), ('id', '!=', lot_id)]",
    )
    max_quantity = fields.Float(
        related="quant_id.quantity",
    )
    quantity = fields.Float(
        required=True,
        help="Quantity to be transfered to the destintation lot.",
    )


    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self._context.get("active_model") == "stock.quant":
            quant = self.env["stock.quant"].browse(self._context.get("active_ids", []))[:1]
            res.update(
                {
                    "quant_id": quant.id,
                    "quantity": quant.quantity,
                }
            )
        return res

    @api.onchange("quantity")
    def _onchange_transfer_quantity(self):
        qty = min(self.quantity, self.max_quantity)
        self.quantity = max(qty, 0.0)

    def action_apply_inventory(self):
        origin_quant = self.quant_id
        dest_quant = self.env["stock.quant"].search(
            [
                ("lot_id", "=", self.dest_lot_id.id),
                ("product_id", "=", self.product_id.id),
                ("location_id", "=", origin_quant.location_id.id),
            ]
        )
        if dest_quant:
            self._cr.execute(
                f"UPDATE stock_quant SET quantity=quantity + {origin_quant.quantity} WHERE id={dest_quant.id};"
            )
            self._cr.execute(
                f"DELETE FROM stock_quant WHERE id={origin_quant.id};"
            )
        else:
            self._cr.execute(
                f"UPDATE stock_quant SET lot_id={self.dest_lot_id.id} WHERE id={origin_quant.id}"
            )
