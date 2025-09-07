import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class IotDevice(models.Model):
    _inherit = "iot.device"

    type = fields.Selection(
        selection_add=[("gps_tracker", "GPS Tracker")],
        ondelete={"gps_tracker": "set default"},
    )

    # GPS-specific fields
    is_gps_device = fields.Boolean(
        string="Is GPS Device",
        compute="_compute_is_gps_device",
        store=True,
    )
    gps_imei = fields.Char(
        string="IMEI",
        index=True,  # Index for IMEI lookups
        help="GPS Device IMEI (International Mobile Equipment Identity)",
    )
    gps_config_id = fields.Many2one(
        "iot.gps.config",
        string="GPS Configuration",
        help="Configuration profile for this GPS device",
    )
    gps_last_latitude = fields.Float(
        string="Last Latitude",
        digits=(10, 7),
        help="Last known latitude position",
    )
    gps_last_longitude = fields.Float(
        string="Last Longitude",
        digits=(10, 7),
        help="Last known longitude position",
    )
    gps_last_position = fields.Char(
        string="Last Position",
        compute="_compute_gps_last_position",
        help="Last known position as coordinates",
    )
    gps_last_update = fields.Datetime(
        string="Last GPS Update",
        index=True,  # Index for connectivity checks
        help="Timestamp of last GPS position update",
    )
    gps_last_speed = fields.Float(
        string="Last Speed (km/h)",
        help="Last recorded speed in km/h",
    )
    gps_last_altitude = fields.Float(
        string="Last Altitude (m)",
        help="Last recorded altitude in meters",
    )
    gps_last_satellites = fields.Integer(
        string="Satellites",
        help="Number of satellites in last fix",
    )
    gps_tracking_enabled = fields.Boolean(
        string="Tracking Enabled",
        default=True,
        index=True,  # Index for filtering active trackers
        help="Enable continuous GPS tracking",
    )
    gps_update_interval = fields.Integer(
        string="Update Interval (seconds)",
        default=30,
        help="GPS position update interval in seconds",
    )
    gps_battery_level = fields.Float(
        string="Battery Level (%)",
        help="Current battery level of GPS device",
    )
    gps_ignition_state = fields.Boolean(
        string="Ignition On",
        help="Vehicle ignition state",
    )
    gps_movement_state = fields.Boolean(
        string="In Movement",
        help="Device is currently moving",
    )

    # Related tracking data
    gps_tracking_point_ids = fields.One2many(
        "iot.gps.tracking.point",
        "iot_device_id",
        string="Tracking Points",
        help="Historical GPS tracking points",
    )
    gps_tracking_point_count = fields.Integer(
        string="Tracking Points",
        compute="_compute_gps_tracking_point_count",
    )

    # Geofence related
    gps_geofence_ids = fields.Many2many(
        "iot.gps.geofence",
        "iot_device_geofence_rel",
        "device_id",
        "geofence_id",
        string="Monitored Geofences",
        help="Geofences being monitored for this device",
    )
    gps_inside_geofence_ids = fields.Many2many(
        "iot.gps.geofence",
        "iot_device_inside_geofence_rel",
        "device_id",
        "geofence_id",
        string="Inside Geofences",
        compute="_compute_inside_geofences",
        help="Geofences the device is currently inside",
    )

    @api.depends("type")
    def _compute_is_gps_device(self):
        for device in self:
            device.is_gps_device = device.type == "gps_tracker"

    @api.depends("gps_last_latitude", "gps_last_longitude")
    def _compute_gps_last_position(self):
        for device in self:
            if device.gps_last_latitude and device.gps_last_longitude:
                device.gps_last_position = (
                    f"{device.gps_last_latitude:.7f}, {device.gps_last_longitude:.7f}"
                )
            else:
                device.gps_last_position = False

    @api.depends("gps_tracking_point_ids")
    def _compute_gps_tracking_point_count(self):
        for device in self:
            device.gps_tracking_point_count = len(device.gps_tracking_point_ids)

    @api.depends("gps_last_latitude", "gps_last_longitude", "gps_geofence_ids")
    def _compute_inside_geofences(self):
        """Compute which geofences the device is currently inside"""
        for device in self:
            inside = self.env["iot.gps.geofence"]
            if device.gps_last_latitude and device.gps_last_longitude:
                for geofence in device.gps_geofence_ids:
                    if geofence._is_point_inside(
                        device.gps_last_latitude, device.gps_last_longitude
                    ):
                        inside |= geofence
            device.gps_inside_geofence_ids = inside

    def action_start_tracking(self):
        """Start GPS tracking for this device"""
        self.ensure_one()
        if not self.is_gps_device:
            raise UserError(_("This action is only available for GPS devices."))

        # Send command to IoT device
        self.env["iot.channel"].send_message(
            {
                "iot_identifiers": [self.iot_id.identifier] if self.iot_id else [],
                "device_identifiers": [self.identifier],
                "action": "start_tracking",
                "session_id": self.env.user.id,
            }
        )

        self.gps_tracking_enabled = True

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("GPS Tracking"),
                "message": _("Tracking started for %s") % self.name,
                "type": "success",
                "sticky": False,
            },
        }

    def action_stop_tracking(self):
        """Stop GPS tracking"""
        self.ensure_one()
        if not self.is_gps_device:
            raise UserError(_("This action is only available for GPS devices."))

        # Send command to IoT device
        self.env["iot.channel"].send_message(
            {
                "iot_identifiers": [self.iot_id.identifier] if self.iot_id else [],
                "device_identifiers": [self.identifier],
                "action": "stop_tracking",
                "session_id": self.env.user.id,
            }
        )

        self.gps_tracking_enabled = False

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("GPS Tracking"),
                "message": _("Tracking stopped for %s") % self.name,
                "type": "info",
                "sticky": False,
            },
        }

    def action_get_current_position(self):
        """Request current position from GPS device"""
        self.ensure_one()
        if not self.is_gps_device:
            raise UserError(_("This action is only available for GPS devices."))

        # Send command to IoT device
        self.env["iot.channel"].send_message(
            {
                "iot_identifiers": [self.iot_id.identifier] if self.iot_id else [],
                "device_identifiers": [self.identifier],
                "action": "get_position",
                "session_id": self.env.user.id,
            }
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("GPS Position"),
                "message": _("Position request sent to %s") % self.name,
                "type": "info",
                "sticky": False,
            },
        }

    def action_view_tracking_points(self):
        """View tracking points for this device"""
        self.ensure_one()
        return {
            "name": _("Tracking Points"),
            "type": "ir.actions.act_window",
            "res_model": "iot.gps.tracking.point",
            "view_mode": "tree,form,geoengine",
            "domain": [("iot_device_id", "=", self.id)],
            "context": {
                "default_iot_device_id": self.id,
                "search_default_last_week": 1,
            },
        }

    def action_view_on_map(self):
        """View device on map"""
        self.ensure_one()
        if not self.gps_last_latitude or not self.gps_last_longitude:
            raise UserError(_("No GPS position available for this device."))

        # This would typically open a map view
        # For now, return a notification with position
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("GPS Position"),
                "message": _("Device %s is at: %s")
                % (self.name, self.gps_last_position),
                "type": "info",
                "sticky": True,
            },
        }

    def process_gps_position(self, position_data):
        """Process incoming GPS position data

        :param position_data: Dictionary with GPS position data
        :return: Created tracking point record
        """
        self.ensure_one()

        # Update device position
        update_vals = {}

        if "latitude" in position_data:
            update_vals["gps_last_latitude"] = position_data["latitude"]
        if "longitude" in position_data:
            update_vals["gps_last_longitude"] = position_data["longitude"]
        if "speed" in position_data:
            update_vals["gps_last_speed"] = position_data["speed"]
        if "altitude" in position_data:
            update_vals["gps_last_altitude"] = position_data["altitude"]
        if "satellites" in position_data:
            update_vals["gps_last_satellites"] = position_data["satellites"]
        if "battery" in position_data:
            update_vals["gps_battery_level"] = position_data["battery"]
        if "ignition" in position_data:
            update_vals["gps_ignition_state"] = position_data["ignition"]
        if "movement" in position_data:
            update_vals["gps_movement_state"] = position_data["movement"]

        update_vals["gps_last_update"] = fields.Datetime.now()

        self.write(update_vals)

        # Create tracking point if tracking is enabled
        if self.gps_tracking_enabled:
            tracking_point = self.env["iot.gps.tracking.point"].create(
                {
                    "iot_device_id": self.id,
                    "timestamp": position_data.get("timestamp", fields.Datetime.now()),
                    "latitude": position_data.get("latitude"),
                    "longitude": position_data.get("longitude"),
                    "altitude": position_data.get("altitude", 0),
                    "speed": position_data.get("speed", 0),
                    "satellites": position_data.get("satellites", 0),
                    "ignition": position_data.get("ignition", False),
                    "movement": position_data.get("movement", False),
                }
            )

            _logger.info(
                f"GPS position recorded for device {self.name}: "
                f"lat={position_data.get('latitude')}, "
                f"lon={position_data.get('longitude')}"
            )

            return tracking_point

        return False

    @api.model
    def create_gps_device(self, imei, initial_data=None):
        """Create a new GPS IoT device

        :param imei: GPS device IMEI
        :param initial_data: Optional initial GPS data
        :return: Created IoT device record
        """
        # Get or create virtual IoT box for GPS devices
        gps_box = self.env["iot.box"].search(
            [("identifier", "=", "gps_virtual_box")], limit=1
        )

        if not gps_box:
            gps_box = self.env["iot.box"].create(
                {
                    "name": "GPS Virtual Box",
                    "identifier": "gps_virtual_box",
                    "ip": "virtual.gps.local",
                    "version": "1.0",
                }
            )

        # Check if device already exists
        existing = self.search(
            [("gps_imei", "=", imei), ("type", "=", "gps_tracker")], limit=1
        )

        if existing:
            return existing

        # Create new device
        device = self.create(
            {
                "name": f"GPS {imei}",
                "identifier": f"gps_{imei}",
                "type": "gps_tracker",
                "iot_id": gps_box.id,
                "connection": "network",
                "gps_imei": imei,
                "connected_status": "connected",
            }
        )

        # Process initial data if provided
        if initial_data:
            device.process_gps_position(initial_data)

        return device

    @api.model
    def _cron_check_gps_device_status(self):
        """Cron job to check GPS device connectivity and alert on issues"""
        from datetime import datetime, timedelta

        _logger.info("Checking GPS device status")

        # Find all GPS devices
        gps_devices = self.search(
            [("type", "=", "gps_tracker"), ("gps_tracking_enabled", "=", True)]
        )

        for device in gps_devices:
            if device.gps_config_id and device.gps_config_id.alert_on_disconnect:
                # Check if device hasn't reported recently
                timeout_minutes = device.gps_config_id.disconnect_timeout / 60
                cutoff_time = datetime.now() - timedelta(minutes=timeout_minutes)

                if device.gps_last_update and device.gps_last_update < cutoff_time:
                    # Device is considered disconnected
                    if device.connected_status != "disconnected":
                        device.connected_status = "disconnected"
                        _logger.warning(
                            f"GPS device {device.name} marked as disconnected"
                        )

                        # TODO: Send notification/alert
                        # This could trigger an email, SMS, or system notification
                elif device.connected_status != "connected":
                    device.connected_status = "connected"
                    _logger.info(f"GPS device {device.name} reconnected")

        _logger.info("GPS device status check completed")
