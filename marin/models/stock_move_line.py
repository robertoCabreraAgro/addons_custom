from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockMoveLineInherit(models.Model):
    _inherit = "stock.move.line"


    move_id = fields.Many2one(ondelete="cascade")
    location_availability = fields.Float(
        "From availability",
        compute="_compute_location_availability",
        readonly=True,
    )
    location_dest_availability = fields.Float(
        "To availability",
        compute="_compute_location_availability",
        readonly=True
    )
    #TODO It seem odoo 18 will solve this natively, delete if so
    location_lot_domain = fields.Binary(
        "Location Lot domain",
        compute="_compute_location_lot_domain",
        help="Dynamic domain used for the lot that can be set on move line",
    )

    @api.onchange("product_id", "location_id", "location_dest_id")
    def _compute_location_availability(self):
        for line in self:
            line.location_availability = 0.0
            line.location_dest_availability = 0.0
            if line.product_id:
                line.location_availability = self.env["stock.quant"]._get_available_quantity(
                    line.product_id, line.location_id, line.lot_id
                )
                line.location_dest_availability = self.env["stock.quant"]._get_available_quantity(
                    line.product_id, line.location_dest_id, line.lot_id
                )

    @api.depends("location_id", "product_id")
    def _compute_location_lot_domain(self):
        for line in self:
            domain = [
                ("company_id", "=", line.company_id.id),
                ("product_id", "=", line.product_id.id)
            ]
            if line.location_usage in ("internal"):
                quant_lot_ids = line.location_id.quant_ids.filtered(
                    lambda q: q.quantity > 0 and q.company_id == line.company_id
                ).mapped("lot_id")
                domain = [("id", "in", quant_lot_ids.ids)]
            line.location_lot_domain = domain

    # Override original method
    @api.ondelete(at_uninstall=False)
    def _unlink_except_done_or_cancel(self):
        for ml in self:
            if ml.state == "done":
                raise UserError(_(
                        "You can not delete product moves if the picking is done. "
                        "You can only correct the done quantities."
                ))
