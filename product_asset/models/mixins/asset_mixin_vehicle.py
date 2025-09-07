import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class AssetMixinVehicle(models.AbstractModel):
    """Vehicle-specific mixin for asset management

    This mixin provides fields and functionality specific to vehicle assets:
    - Vehicle identification (license plate, VIN, engine serial)
    - Vehicle specifications (model year, fuel type, transmission)
    - Vehicle features (trailer hook, doors, seats)
    - Odometer tracking and fuel tank capacity
    """

    _name = "asset.mixin.vehicle"
    _description = "Asset Vehicle Mixin"

    # ------------------------------------------------------------
    # VEHICLE IDENTIFICATION FIELDS
    # ------------------------------------------------------------

    license_plate = fields.Char(
        string="License Plate",
        copy=False,
        tracking=True,
        help="License plate number of the vehicle",
    )
    vin_sn = fields.Char(
        string="Chassis Number (VIN)",
        copy=False,
        tracking=True,
        help="Vehicle Identification Number (VIN) or chassis serial number",
    )
    engine_sn = fields.Char(
        string="Engine Serial Number",
        copy=False,
        tracking=True,
        help="Unique serial number of the vehicle engine",
    )

    # ------------------------------------------------------------
    # VEHICLE SPECIFICATIONS
    # ------------------------------------------------------------

    model_year = fields.Char(
        string="Model Year",
        help="Manufacturing year of the vehicle model",
    )
    fuel_tank_capacity = fields.Integer(
        string="Tank Capacity",
        help="Fuel tank capacity in liters",
    )
    trailer_hook = fields.Boolean(
        string="Trailer Hitch",
        default=False,
        help="Indicates if the vehicle has a trailer hitch installed",
    )

    # Physical specifications from product template
    doors = fields.Integer(
        string="Number of Doors",
        related="product_id.doors",
        readonly=True,
        help="Number of doors on the vehicle",
    )

    seats = fields.Integer(
        string="Number of Seats",
        related="product_id.seats",
        readonly=True,
        help="Number of passenger seats in the vehicle",
    )

    # ------------------------------------------------------------
    # ODOMETER TRACKING
    # ------------------------------------------------------------

    odometer = fields.Float(
        string="Odometer",
        compute="_compute_odometer",
        store=True,
        help="Current odometer reading",
    )

    odometer_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Odometer Unit",
        default=lambda self: self.env.ref("uom.product_uom_km", False),
        tracking=True,
        help="Unit of measurement for odometer readings (km or miles)",
    )

    # ------------------------------------------------------------
    # FUEL AND PERFORMANCE
    # ------------------------------------------------------------

    fuel_type = fields.Selection(
        selection=[
            ("gasoline", "Gasoline"),
            ("diesel", "Diesel"),
            ("electric", "Electric"),
            ("hybrid_gasoline", "Hybrid (Gasoline)"),
            ("hybrid_diesel", "Hybrid (Diesel)"),
            ("lpg", "LPG"),
            ("cng", "CNG"),
            ("hydrogen", "Hydrogen"),
        ],
        string="Fuel Type",
        help="Type of fuel or energy source used by the vehicle",
    )

    transmission = fields.Selection(
        selection=[
            ("manual", "Manual"),
            ("automatic", "Automatic"),
            ("cvt", "CVT"),
            ("semi_auto", "Semi-Automatic"),
            ("dual_clutch", "Dual Clutch"),
        ],
        string="Transmission Type",
        help="Type of transmission system in the vehicle",
    )

    power = fields.Integer(
        related="product_id.power",
        string="Power (kW)",
        readonly=True,
        help="Engine power in kilowatts",
    )

    co2_emissions = fields.Float(
        related="product_id.co2",
        string="CO2 Emissions",
        readonly=True,
        help="CO2 emissions in g/km",
    )

    # Fuel efficiency from product template
    fuel_efficiency_theoretical = fields.Float(
        related="product_id.fuel_efficiency_theoretical",
        string="Theoretical Fuel Efficiency",
        readonly=True,
        help="Manufacturer stated fuel efficiency",
    )

    # ------------------------------------------------------------
    # VEHICLE FEATURES
    # ------------------------------------------------------------

    color = fields.Char(
        string="Color",
        help="Vehicle color",
    )

    area = fields.Integer(
        string="Cargo Area",
        help="Cargo area in square meters (for trucks/vans)",
    )

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    @api.depends("log_ids.value")
    def _compute_odometer(self):
        """Compute current odometer reading from the latest log entry"""
        for vehicle in self:
            try:
                # Get all logs with odometer readings, sorted by date descending
                odometer_logs = vehicle.log_ids.filtered(
                    lambda log: hasattr(log, "value") and log.value > 0
                ).sorted(
                    lambda log: (
                        log.date if hasattr(log, "date") else fields.Date.today()
                    ),
                    reverse=True,
                )

                # Use the most recent odometer reading
                if odometer_logs:
                    vehicle.odometer = odometer_logs[0].value
                else:
                    vehicle.odometer = 0.0

            except Exception as e:
                _logger.warning(
                    f"Error computing odometer for vehicle {vehicle.id}: {e}"
                )
                vehicle.odometer = 0.0

    # ------------------------------------------------------------
    # HELPER METHODS
    # ------------------------------------------------------------

    def get_vehicle_name(self):
        """Get a formatted name for the vehicle"""
        self.ensure_one()

        parts = []

        # Add brand/manufacturer if available
        if hasattr(self, "product_id") and self.product_id:
            if self.product_id.manufacturer_id:
                parts.append(self.product_id.manufacturer_id.name)
            if self.product_id.model_id:
                parts.append(self.product_id.model_id.name)

        # Add model year
        if self.model_year:
            parts.append(f"({self.model_year})")

        # Add license plate
        if self.license_plate:
            parts.append(f"[{self.license_plate}]")

        return " ".join(parts) if parts else _("Vehicle")

    def update_odometer(self, new_value, date=None):
        """Update the vehicle odometer with a new reading

        Args:
            new_value: New odometer reading
            date: Date of the reading (default: today)
        """
        self.ensure_one()

        if new_value <= 0:
            return False

        # Create an odometer log entry
        log_vals = {
            "asset_id": self.id,
            "date": date or fields.Date.today(),
            "value": new_value,
            "description": f'Odometer update: {new_value} {self.odometer_uom_id.name if self.odometer_uom_id else "km"}',
            "state": "done",
        }

        return self.env["product.asset.log"].create(log_vals)

    def calculate_fuel_efficiency(self, start_odometer, end_odometer, fuel_consumed):
        """Calculate actual fuel efficiency based on consumption

        Args:
            start_odometer: Starting odometer reading
            end_odometer: Ending odometer reading
            fuel_consumed: Fuel consumed in liters

        Returns:
            Fuel efficiency in km/L or miles/gallon depending on UOM
        """
        self.ensure_one()

        if end_odometer <= start_odometer or fuel_consumed <= 0:
            return 0.0

        distance = end_odometer - start_odometer
        efficiency = distance / fuel_consumed

        return efficiency

    def get_vehicle_info(self):
        """Get comprehensive vehicle information dictionary"""
        self.ensure_one()

        return {
            "identification": {
                "license_plate": self.license_plate,
                "vin": self.vin_sn,
                "engine_serial": self.engine_sn,
            },
            "specifications": {
                "model_year": self.model_year,
                "fuel_type": self.fuel_type,
                "transmission": self.transmission,
                "doors": self.doors,
                "seats": self.seats,
                "color": self.color,
            },
            "performance": {
                "power_kw": self.power,
                "co2_emissions": self.co2_emissions,
                "fuel_efficiency": self.fuel_efficiency_theoretical,
                "tank_capacity": self.fuel_tank_capacity,
            },
            "current_status": {
                "odometer": self.odometer,
                "odometer_unit": (
                    self.odometer_uom_id.name if self.odometer_uom_id else "km"
                ),
            },
        }
