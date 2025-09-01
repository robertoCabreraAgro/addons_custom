from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class StockMoveLine(models.Model):
    """Inherit StockMoveLine"""

    _inherit = "stock.move.line"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    move_id = fields.Many2one(ondelete="cascade")
    location_availability = fields.Float(
        "From availability",
        compute="_compute_location_availability",
        readonly=True,
    )
    location_dest_availability = fields.Float(
        "To availability", compute="_compute_location_availability", readonly=True
    )

    @api.onchange("product_id", "location_id", "location_dest_id")
    def _compute_location_availability(self):
        for line in self:
            line.location_availability = 0.0
            line.location_dest_availability = 0.0
            if line.product_id:
                line.location_availability = self.env[
                    "stock.quant"
                ]._get_available_quantity(
                    line.product_id, line.location_id, line.lot_id
                )
                line.location_dest_availability = self.env[
                    "stock.quant"
                ]._get_available_quantity(
                    line.product_id, line.location_dest_id, line.lot_id
                )

    # Override original method
    @api.ondelete(at_uninstall=False)
    def _unlink_except_done_or_cancel(self):
        for ml in self:
            if ml.state == "done":
                raise UserError(
                    _(
                        "You can not delete product moves if the picking is done. "
                        "You can only correct the done quantities."
                    )
                )
