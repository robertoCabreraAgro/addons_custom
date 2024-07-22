import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class StockQuantLotWizard(models.TransientModel):
    _name = "stock.quant.lot"
    _description = "Change Quant Lot Wizard"

    quant_id = fields.Many2one(
        "stock.quant",
        required=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        "product.product",
        related="quant_id.product_id",
        readonly=True,
        required=True,
    )
    lot_id = fields.Many2one(
        "stock.lot",
        related="quant_id.lot_id",
        readonly=True,
        required=True,
    )
    dest_lot_id = fields.Many2one(
        "stock.lot",
        required=True,
        domain="[('product_id', '=', product_id), ('id', '!=', lot_id)]",
        string="Destination Lot",
    )
    max_quantity = fields.Float(related="quant_id.quantity")
    quantity = fields.Float(required=True, help="Quantity to be transfered to the destintation lot.")

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
    def _onchange_transfer_quantit(self):
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
        if not dest_quant:
            dest_quant = quant_obj.create(
                {
                    "lot_id": self.dest_lot_id.id,
                    "product_id": self.product_id.id,
                    "location_id": quant.location_id.id,
                }
            )
        quant.inventory_quantity = quant.quantity - self.quantity
        dest_quant.inventory_quantity = dest_quant.quantity + self.quantity
        (quant | dest_quant).action_apply_inventory()
