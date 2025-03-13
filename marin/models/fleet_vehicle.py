from odoo import _, api, fields, models


class FleetVehicleInherit(models.Model):
    _inherit = "fleet.vehicle"


    department_id = fields.Many2one(
        comodel_name="hr.department",
        string="Department"
    )
    fuel_card_id = fields.Many2one(
        comodel_name="documents.document",
        domain=lambda self: [
            ("tag_ids", "in", self.env.ref("marin_data.documents_fleet_fuel_card").ids),
        ],
        inverse="_inverse_fuel_card_id",
        store=True,
        readonly=False,
    )
    fuel_card_name = fields.Char(compute="_compute_fuel_card_name", store=True)
    highway_pass_id = fields.Many2one(
        comodel_name="documents.document",
        domain=lambda self: [
            ("tag_ids", "in", self.env.ref("marin_data.documents_fleet_highway_pass").ids),
        ],
        inverse="_inverse_highway_pass_id",
        store=True,
        readonly=False,
    )
    highway_pass_name = fields.Char(compute="_compute_highway_pass_name", store=True)
    l10n_mx_vehicle_code = fields.Char(
        string='Vehicle Code',
        tracking=True,
        help='In Mexico the tax authority assign a 7 character code to identify its characteristics.',
    )
    account_prefix = fields.Char(
        string='Account Prefix',
        tracking=True,
        help='This fields is required by Accounting to group according to its needs.',
    )
    brand_new = fields.Boolean(
        string='Brand New',
        default=True,
        help="Mark as True if this vehicle was acquired as brand new.",
    )


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
                name = name.replace("Efecticard ", "")
            vehicle.fuel_card_name = name

    @api.depends("highway_pass_id")
    def _compute_highway_pass_name(self):
        for vehicle in self:
            name = ""
            if vehicle.highway_pass_id:
                name = vehicle.highway_pass_id.name.split(".", 1)[0]
                name = name.replace("IMDM ", "")
            vehicle.highway_pass_name = name

    def _inverse_fuel_card_id(self):
        """
        Set the vehicle on the corresponding document, and unset the vehicle on 
        previously related documents
        """
        tag = self.env.ref("marin_data.documents_fleet_fuel_card", False)
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
        tag = self.env.ref("marin_data.documents_fleet_highway_pass", False)
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

    def _get_gps_tracking_device(self, date=False):
        self.ensure_one()
        domain = [("vehicle_id", "=", self.id)]
        if date:
            domain += [("timestamp", "<", date)]

        return self.env["gps.tracking.device"].search(domain, order="id desc", limit=1)

    def _get_gps_odometer(self, date=False):
        """Get odometer reading from GPS"""
        self.ensure_one()
        gps_device = self._get_gps_tracking_device(date=date)
        return round(gps_device.last_point_id.odometer / 1000, 2)

    def _get_gps_fuel_level(self, date=False):
        """Get fuel level reading from GPS"""
        self.ensure_one()
        gps_device = self._get_gps_tracking_device(date=date)
        return round(gps_device.last_point_id.fuel_level, 2)

    def _compute_odometer(self):
        gps_vehicles = self.env["fleet.vehicle"]
        for vehicle in self:
            vehicle.odometer = vehicle._get_gps_odometer()
            if vehicle.odometer:
                gps_vehicles |= vehicle
        return super(FleetVehicleInherit, self - gps_vehicles)._compute_odometer()
