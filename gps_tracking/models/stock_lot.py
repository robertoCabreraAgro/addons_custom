from odoo import fields, models


class StockLot(models.Model):
    _inherit = "stock.lot"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    gps_device_id = fields.Many2one(
        comodel_name="gps.tracking.device",
        string="GPS Device",
        help="GPS tracking device associated with this vehicle",
    )
