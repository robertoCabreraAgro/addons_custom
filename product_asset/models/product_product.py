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
        compute="_compute_vehicle_name",
        store=True,
    )

    @api.depends("name", "manufacturer_id.name", "lot_ids.license_plate")
    def _compute_vehicle_name(self):
        for vehicle in self:
            if vehicle.asset_type == "product":
                vehicle.vehicle_name = ""
            else:
                vehicle.vehicle_name = (
                    (vehicle.manufacturer_id.name or "")
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
