from odoo import api, fields, models


class GpsTrackingConfig(models.Model):
    _name = "gps.tracking.config"
    _description = "GPS Tracking Configuration"
    _rec_name = "name"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

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
    fuel_reading = fields.Selection(
        selection=[
            ("percentage", "As Percentage of tank capacity"),
            ("volume", "As Volume (Deciliters)"),
            ("percentage_volumen", "Both Percentage and Volume"),
        ],
        string="Fuel Reading Type",
    )
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
        string="Notes",
        help="Additional notes about this configuration",
    )
    device_ids = fields.One2many(
        comodel_name="gps.tracking.device",
        inverse_name="config_id",
        string="Associated Devices",
        help="Devices using this configuration",
    )
    count_device_ids = fields.Integer(
        string="Device Count",
        compute="_compute_count_device_ids",
        help="Number of devices using this configuration",
    )

    # ------------------------------------------------------------
    # CONSTRAINTS
    # ------------------------------------------------------------

    @api.constrains("odometer_correction_factor")
    def _check_odometer_correction_factor(self):
        """Validate odometer correction factor is positive."""
        for config in self:
            if config.odometer_correction_factor <= 0:
                raise ValueError("Odometer correction factor must be positive")

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    @api.depends("device_ids")
    def _compute_count_device_ids(self):
        """Compute the number of devices using this configuration."""
        for config in self:
            config.count_device_ids = len(config.device_ids)

    # ------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------

    def get_corrected_odometer(self, raw_odometer):
        """Apply correction factor to raw odometer reading.

        Args:
            raw_odometer (float): Raw odometer value from device

        Returns:
            float: Corrected odometer value
        """
        self.ensure_one()
        return raw_odometer * self.odometer_correction_factor
