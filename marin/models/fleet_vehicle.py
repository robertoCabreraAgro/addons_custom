from odoo import _, api, fields, models


class FleetVehicleInherit(models.Model):
    _inherit = "fleet.vehicle"


    fuel_tank_capacity = fields.Integer(
        string="Tank capacity",
        help="Fuel tank capacity in liters",
    )
    cilinders = fields.Integer(string="Cilinders Number")
    fuel_efficiency = fields.Float(
        help="Fuel efficiency in kilometers per liter (km/L)"
    )
    fuel_card_id = fields.Many2one(
        "documents.document",
        domain=lambda self: [
            ("tag_ids", "in", self.env.ref("marin.documents_fleet_fuel_card").ids),
            ("vehicle_id", "in", (self.id, False)),
        ],
        inverse="_inverse_fuel_card_id",
        store=True,
        readonly=False,
    )
    fuel_card_name = fields.Char(compute="_compute_fuel_card_name", store=True)
    highway_pass_id = fields.Many2one(
        "documents.document",
        domain=lambda self: [
            ("tag_ids", "in", self.env.ref("marin.documents_fleet_highway_pass").ids),
            ("vehicle_id", "in", (self.id, False)),
        ],
        inverse="_inverse_highway_pass_id",
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
        for vehicle in self:
            name = ""
            if vehicle.fuel_card_id:
                name = vehicle.fuel_card_id.name.split(".", 1)[0]
                name.replace("Efecticard ", "")
            vehicle.fuel_card_name = name

    @api.depends("highway_pass_id")
    def _compute_highway_pass_name(self):
        for vehicle in self:
            name = ""
            if vehicle.highway_pass_id:
                name = vehicle.highway_pass_id.name.split(".", 1)[0]
                name.replace("IMDM ", "")
            vehicle.highway_pass_name = name

    def _inverse_fuel_card_id(self):
        """
        Set the vehicle on the corresponding document, and unset the vehicle on 
        previously related documents
        """
        tag = self.env.ref("marin.documents_fleet_fuel_card", False)
        for vehicle in self:
            doc = vehicle.fuel_card_id
            other_docs = doc.search(
                [("vehicle_id", "=", vehicle.id), ("tag_ids", "in", tag.ids)]
            ) - doc
            if doc:
                doc.write(
                    {
                        "res_model": vehicle._name,
                        "res_id": vehicle.id,
                        "is_editable_attachment": True,
                        "vehicle_id": vehicle.id,
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

    def _inverse_highway_pass_id(self):
        """
        Set the vehicle on the corresponding document, and unset the vehicle on
        previously related documents
        """
        tag = self.env.ref("marin.documents_fleet_highway_pass", False)
        for vehicle in self:
            doc = vehicle.highway_pass_id
            other_docs = doc.search(
                [("vehicle_id", "=", vehicle.id), ("tag_ids", "in", tag.ids)]
            ) - doc
            if doc:
                doc.write(
                    {
                        "res_model": vehicle._name,
                        "res_id": vehicle.id,
                        "is_editable_attachment": True,
                        "vehicle_id": vehicle.id,
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
