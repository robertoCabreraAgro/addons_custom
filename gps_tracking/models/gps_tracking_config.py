from odoo import api, fields, models


class GpsTrackingConfig(models.Model):
    _name = "gps.tracking.config"
    _description = "GPS Tracking Configuration"
    _rec_name = "name"

    name = fields.Char(
        string="Configuration Name",
        required=True,
        default=lambda self: self.env["ir.sequence"].next_by_code(
            "gps.tracking.config"
        ),
        copy=False,
        help="Name to identify this GPS tracking configuration",
    )

    # Odometer configuration
    reports_odometer = fields.Boolean(
        string="Reports Odometer",
        default=True,
        help="Whether this device reports odometer field (if False, uses total_odometer)",
    )
    odometer_correction_factor = fields.Float(
        string="Odometer Correction Factor",
        default=1.0,
        help="Factor to correct odometer readings (e.g., 0.001 to convert from meters to kilometers)",
    )

    # Fuel configuration
    reports_fuel_percentage = fields.Boolean(
        string="Reports Fuel Percentage",
        default=True,
        help="Whether this device reports fuel level as percentage",
    )
    reports_fuel_volume = fields.Boolean(
        string="Reports Fuel Volume (Deciliters)",
        default=False,
        help="Whether this device reports fuel volume in deciliters",
    )
    reports_historical_consumption = fields.Boolean(
        string="Reports Historical Fuel Consumption",
        default=False,
        help="Whether this device tracks historical fuel consumption",
    )

    notes = fields.Text(
        string="Notes", help="Additional notes about this configuration"
    )

    # Related devices
    device_ids = fields.One2many(
        comodel_name="gps.tracking.device",
        inverse_name="config_id",
        string="Associated Devices",
        help="Devices using this configuration",
    )
    device_count = fields.Integer(
        string="Device Count",
        compute="_compute_device_count",
        help="Number of devices using this configuration",
    )

    @api.depends("device_ids")
    def _compute_device_count(self):
        """Compute the number of devices using this configuration."""
        for config in self:
            config.device_count = len(config.device_ids)

    @api.constrains("odometer_correction_factor")
    def _check_odometer_correction_factor(self):
        """Validate odometer correction factor is positive."""
        for config in self:
            if config.odometer_correction_factor <= 0:
                raise ValueError("Odometer correction factor must be positive")

    def get_corrected_odometer(self, raw_odometer):
        """Apply correction factor to raw odometer reading.

        Args:
            raw_odometer (float): Raw odometer value from device

        Returns:
            float: Corrected odometer value
        """
        self.ensure_one()
        if not raw_odometer:
            return 0.0
        return raw_odometer * self.odometer_correction_factor

    def get_fuel_level_liters(
        self, fuel_percentage=None, fuel_deciliters=None, vehicle=None
    ):
        """Get fuel level in liters based on configuration.

        Args:
            fuel_percentage (float): Fuel level as percentage (0-100)
            fuel_deciliters (float): Fuel level in deciliters
            vehicle (stock.lot): Vehicle record to get tank capacity from

        Returns:
            float: Fuel level in liters, or False if cannot be determined
        """
        self.ensure_one()

        # If device reports volume directly, convert from deciliters to liters
        if self.reports_fuel_volume and fuel_deciliters is not None:
            return fuel_deciliters / 10.0  # Convert deciliters to liters

        # If device reports percentage and we have tank capacity, convert it
        if (
            self.reports_fuel_percentage
            and fuel_percentage is not None
            and vehicle
            and vehicle.product_id.fuel_tank_capacity
        ):
            return (fuel_percentage / 100.0) * vehicle.product_id.fuel_tank_capacity

        return False

    def get_fuel_level_percentage(
        self, fuel_percentage=None, fuel_deciliters=None, vehicle=None
    ):
        """Get fuel level as percentage based on configuration.

        Args:
            fuel_percentage (float): Fuel level as percentage (0-100)
            fuel_deciliters (float): Fuel level in deciliters
            vehicle (stock.lot): Vehicle record to get tank capacity from

        Returns:
            float: Fuel level as percentage, or False if cannot be determined
        """
        self.ensure_one()

        # If device reports percentage directly, use it
        if self.reports_fuel_percentage and fuel_percentage is not None:
            return fuel_percentage

        # If device reports deciliters and we have tank capacity, convert it
        if (
            self.reports_fuel_volume
            and fuel_deciliters is not None
            and vehicle
            and vehicle.product_id.fuel_tank_capacity
        ):
            fuel_liters = fuel_deciliters / 10.0  # Convert deciliters to liters
            return (fuel_liters / vehicle.product_id.fuel_tank_capacity) * 100.0

        return False
