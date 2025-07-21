from datetime import datetime
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    gps_device_ids = fields.One2many(
        comodel_name="gps.tracking.device",
        inverse_name="vehicle_id",
        string="GPS Devices",
        help="GPS tracking devices associated with this vehicle",
    )

    def get_odometer_at(self, target_datetime):
        """Get odometer reading at specific datetime using real_odometer field.

        Args:
            target_datetime (datetime): Target datetime for odometer reading

        Returns:
            float: Odometer value from real_odometer field or False if not available
        """
        self.ensure_one()

        # Find the primary GPS device (first active device with configuration)
        device = self.gps_device_ids.filtered(lambda d: d.config_id)[:1]

        if not device:
            return False

        # Find the closest tracking point to the target datetime
        point = self.env["gps.tracking.point"].search(
            [("device_id", "=", device.id), ("timestamp", "<=", target_datetime)],
            order="timestamp desc",
            limit=1,
        )

        if not point:
            return False

        return point.real_odometer

    def get_fuel_at(self, target_datetime):
        """Get fuel level at specific datetime using GPS configuration.

        Args:
            target_datetime (datetime): Target datetime for fuel reading

        Returns:
            dict: Dictionary with fuel data or False if not available
        """
        self.ensure_one()

        # Find the primary GPS device (first active device with configuration)
        device = self.gps_device_ids.filtered(lambda d: d.config_id)[:1]

        if not device:
            return False

        return device.get_fuel_at(target_datetime)

    def get_current_odometer(self):
        """Get current odometer reading from GPS tracking.

        Returns:
            float: Current odometer value or False if not available
        """
        return self.get_odometer_at(datetime.now())

    def get_current_fuel(self):
        """Get current fuel level from GPS tracking.

        Returns:
            dict: Dictionary with current fuel data or False if not available
        """
        return self.get_fuel_at(datetime.now())

    @api.constrains("gps_device_ids")
    def _check_gps_device_configuration(self):
        """Validate that all GPS devices have configuration."""
        for vehicle in self:
            for device in vehicle.gps_device_ids:
                if not device.config_id:
                    raise ValidationError(
                        f"GPS device {device.imei} assigned to vehicle {vehicle.name} "
                        "must have a configuration"
                    )
