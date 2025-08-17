from odoo import _, api, fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    lot_ids = fields.One2many(
        "stock.lot",
        "product_id",
        "Lots",
        readonly=True,
    )
    vehicle_name = fields.Char(
        # compute="_compute_vehicle_name",
        # store=True,
    )
    count_lot_ids = fields.Integer(
        compute="_compute_count_lot_ids",
        string="Lots Count",
    )

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    def _compute_count_lot_ids(self):
        for product in self:
            product.count_lot_ids = product.env[
                "stock.lot"
            ].search_count(
                [
                    ("product_id", "in", product.ids),
                ]
            )

    @api.depends("name", "manufacturer_id.name", "lot_ids.license_plate")
    def _compute_vehicle_name(self):
        for vehicle in self:
            if vehicle.asset_type == "product":
                vehicle.vehicle_name = ""
            else:
                vehicle.vehicle_name = (
                    (vehicle.manufacturer_id.name if vehicle.manufacturer_id else "")
                    + "/"
                    + (vehicle.name or "")
                    + "/"
                    + (
                        vehicle.lot_ids[-1].license_plate
                        if vehicle.lot_ids
                        else _("No Plate")
                    )
                )
                # vehicle.name = f"{vehicle.manufacturer_id.name or ""}/{vehicle.model_id.name or ""}/{vehicle.license_plate or _("No Plate")}"
