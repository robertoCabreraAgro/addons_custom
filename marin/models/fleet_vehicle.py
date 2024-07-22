from odoo import _, api, fields, models


class FleetVehicleInherit(models.Model):
    _inherit = "fleet.vehicle"

    fuel_tank_capacity = fields.Float(
        "Tank capacity",
        help="Fuel tank capacity in liters",
    )
    cilinders = fields.Float("Cilinders Number")
    fuel_card_id = fields.Many2one(
        "documents.document",
        domain=lambda self: [
            ("tag_ids", "in", self.env.ref("marin.documents_fleet_fuel_card", False).ids),
            "|",
            ("vehicle_id", "=", self.id),
            ("vehicle_id", "=", False),
        ],
        inverse="_inverse_fuel_card",
        store=True,
        readonly=False,
    )
    fuel_card_name = fields.Char(compute="_compute_fuel_card_name", store=True)
    highway_pass_id = fields.Many2one(
        "documents.document",
        domain=lambda self: [
            ("tag_ids", "in", self.env.ref("marin.documents_fleet_highway_pass", False).ids),
            "|",
            ("vehicle_id", "=", self.id),
            ("vehicle_id", "=", False),
        ],
        inverse="_inverse_highway_pass",
        store=True,
        readonly=False,
    )
    highway_pass_name = fields.Char(compute="_compute_highway_pass_name", store=True)

    # Extend original method
    @api.depends("model_id.brand_id.name", "model_id.name", "model_year", "color", "license_plate")
    def _compute_vehicle_name(self):
        for vehicle in self:
            vehicle.name = "%s/%s %s/%s/%s" % (
                vehicle.model_id.brand_id.name or "",
                vehicle.model_id.name or "",
                vehicle.model_year or "",
                vehicle.color or "",
                vehicle.license_plate or _("No Plate"),
            )

    @api.depends("fuel_card_id")
    def _compute_fuel_card_name(self):
        for rec in self:
            rec.fuel_card_name = rec.fuel_card_id.name.split(".", 1)[0] if rec.fuel_card_id else ""

    def _inverse_fuel_card(self):
        """Set the vehicle on the corresponding document, and unset the vehicle on previously related documents"""
        tag = self.env.ref("marin.documents_fleet_fuel_card", False)
        for rec in self:
            doc = rec.fuel_card_id
            other_docs = doc.search([("vehicle_id", "=", rec.id), ("tag_ids", "in", tag.ids)]) - doc
            if doc:
                doc.write(
                    {
                        "res_model": rec._name,
                        "res_id": rec.id,
                        "is_editable_attachment": True,
                        "vehicle_id": rec.id,
                    }
                )
            for od in other_docs:
                od.write(
                    {
                        "res_model": od._name,
                        "res_id": od.id,
                        "vehicle_id": False,
                    }
                )

    @api.depends("highway_pass_id")
    def _compute_highway_pass_name(self):
        for rec in self:
            rec.highway_pass_name = rec.highway_pass_id.name.split(".", 1)[0] if rec.highway_pass_id else ""

    def _inverse_highway_pass(self):
        """Set the vehicle on the corresponding document, and unset the vehicle on previously related documents"""
        tag = self.env.ref("marin.documents_fleet_highway_pass", False)
        for rec in self:
            doc = rec.highway_pass_id
            other_docs = doc.search([("vehicle_id", "=", rec.id), ("tag_ids", "in", tag.ids)]) - doc
            if doc:
                doc.write(
                    {
                        "res_model": rec._name,
                        "res_id": rec.id,
                        "is_editable_attachment": True,
                        "vehicle_id": rec.id,
                    }
                )
            for od in other_docs:
                od.write(
                    {
                        "res_model": od._name,
                        "res_id": od.id,
                        "vehicle_id": False,
                    }
                )
