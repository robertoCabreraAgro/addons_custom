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
    lot_rule_id = fields.Many2one(
        comodel_name="stock.lot.rule",
        string="Lot Rule",
        help="Rule used for this lot nomenclature and date calculations",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self._context.get("active_model") == "stock.quant":
            quant = self.env["stock.quant"].browse(self._context.get("active_ids", []))[
                :1
            ]
            res.update(
                {
                    "quant_id": quant.id,
                    "quantity": quant.quantity,
                    "product_id": quant.product_id.id,
                    "lot_id": quant.lot_id.id,
                    "lot_rule_id": quant.lot_id.lot_rule_id.id if quant.lot_id else quant.product_id.lot_rule_id.id,
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
            dest_quant.write(
                {
                    "quantity": dest_quant.quantity + self.quantity,
                }
            )
        else:
            dest_quant = self.env["stock.quant"].create(
                {
                    "location_id": origin_quant.location_id.id,
                    "product_id": self.product_id.id,
                    "lot_id": self.dest_lot_id.id,
                    "quantity": self.quantity,
                }
            )

        origin_quant.write(
            {
                "quantity": origin_quant.quantity - self.quantity,
            }
        )
