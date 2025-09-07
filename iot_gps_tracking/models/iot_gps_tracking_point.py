import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class IoTGpsTrackingPoint(models.Model):
    _name = "iot.gps.tracking.point"
    _description = "IoT GPS Tracking Point"
    _order = "timestamp desc"
    _rec_name = "timestamp"

    # Device reference
    iot_device_id = fields.Many2one(
        "iot.device",
        string="IoT GPS Device",
        required=True,
        domain=[("type", "=", "gps_tracker")],
        ondelete="cascade",
        index=True,  # Index for device lookups
        help="IoT GPS device that recorded this point",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="iot_device_id.company_id",
        store=True,
        readonly=True,
        index=True,  # Index for multi-company filtering
        help="Company from the IoT device",
    )

    # Timestamp
    timestamp = fields.Datetime(
        string="Timestamp",
        required=True,
        index=True,  # Index for time-based queries
        default=fields.Datetime.now,
        help="When this position was recorded",
    )

    # Position data
    latitude = fields.Float(
        string="Latitude",
        digits=(10, 7),
        required=True,
        index=True,  # Index for geographic queries
        help="GPS Latitude coordinate",
    )
    longitude = fields.Float(
        string="Longitude",
        digits=(10, 7),
        required=True,
        index=True,  # Index for geographic queries
        help="GPS Longitude coordinate",
    )
    the_point = fields.GeoPoint(
        string="Point",
        compute="_compute_the_point",
        store=True,
        help="Geographic point for map display",
    )

    # Motion data
    altitude = fields.Float(
        string="Altitude (m)",
        help="Altitude in meters above sea level",
    )
    speed = fields.Float(
        string="Speed (km/h)",
        help="Speed in kilometers per hour",
    )
    heading = fields.Float(
        string="Heading",
        help="Direction in degrees (0-360)",
    )

    # GPS quality
    satellites = fields.Integer(
        string="Satellites",
        help="Number of GPS satellites in view",
    )
    accuracy = fields.Float(
        string="Accuracy (m)",
        help="GPS accuracy in meters",
    )
    hdop = fields.Float(
        string="HDOP",
        help="Horizontal Dilution of Precision",
    )
    pdop = fields.Float(
        string="PDOP",
        help="Position Dilution of Precision",
    )

    # Vehicle telemetry
    ignition = fields.Boolean(
        string="Ignition",
        help="Vehicle ignition state",
    )
    movement = fields.Boolean(
        string="Movement",
        help="Vehicle is moving",
    )
    odometer = fields.Float(
        string="Odometer (km)",
        help="Odometer reading in kilometers",
    )
    total_odometer = fields.Float(
        string="Total Odometer (km)",
        help="Total odometer reading in kilometers",
    )
    fuel_level = fields.Float(
        string="Fuel Level (%)",
        help="Fuel level percentage",
    )
    fuel_consumed = fields.Float(
        string="Fuel Consumed (L)",
        help="Fuel consumed in liters",
    )
    engine_hours = fields.Float(
        string="Engine Hours",
        help="Total engine running hours",
    )
    engine_temp = fields.Float(
        string="Engine Temperature (°C)",
        help="Engine temperature in Celsius",
    )
    engine_rpm = fields.Float(
        string="Engine RPM",
        help="Engine revolutions per minute",
    )

    # Power and sensors
    battery_voltage = fields.Float(
        string="Battery Voltage (V)",
        help="Vehicle battery voltage",
    )
    external_voltage = fields.Float(
        string="External Voltage (V)",
        help="External power supply voltage",
    )
    gsm_signal = fields.Integer(
        string="GSM Signal",
        help="GSM signal strength",
    )

    # Event data
    event_type = fields.Char(
        string="Event Type",
        help="Type of event that triggered this point",
    )
    priority = fields.Integer(
        string="Priority",
        help="Event priority",
    )

    # Additional data
    iot_session_id = fields.Integer(
        string="IoT Session",
        help="IoT session ID when this point was recorded",
    )
    source = fields.Selection(
        selection=[
            ("webhook", "Webhook"),
            ("iot", "IoT Channel"),
            ("manual", "Manual"),
            ("import", "Imported"),
        ],
        string="Source",
        default="iot",
        index=True,  # Index for filtering by source
        help="Source of this tracking point",
    )

    # Computed fields
    distance_from_previous = fields.Float(
        string="Distance from Previous (km)",
        compute="_compute_distance_from_previous",
        help="Distance from previous point in kilometers",
    )
    time_from_previous = fields.Float(
        string="Time from Previous (min)",
        compute="_compute_time_from_previous",
        help="Time from previous point in minutes",
    )

    @api.depends("latitude", "longitude")
    def _compute_the_point(self):
        """Compute GeoPoint from latitude and longitude"""
        for point in self:
            if point.latitude and point.longitude:
                point.the_point = f"POINT({point.longitude} {point.latitude})"
            else:
                point.the_point = False

    @api.depends("iot_device_id", "timestamp")
    def _compute_distance_from_previous(self):
        """Compute distance from previous point"""
        for point in self:
            if point.iot_device_id and point.timestamp:
                previous = self.search(
                    [
                        ("iot_device_id", "=", point.iot_device_id.id),
                        ("timestamp", "<", point.timestamp),
                    ],
                    order="timestamp desc",
                    limit=1,
                )
                if previous:
                    # Simple distance calculation (Haversine formula would be better)
                    from math import radians, cos, sin, asin, sqrt

                    lon1, lat1 = radians(point.longitude), radians(point.latitude)
                    lon2, lat2 = radians(previous.longitude), radians(previous.latitude)

                    dlon = lon2 - lon1
                    dlat = lat2 - lat1
                    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
                    c = 2 * asin(sqrt(a))
                    km = 6371 * c  # Radius of earth in kilometers

                    point.distance_from_previous = km
                else:
                    point.distance_from_previous = 0
            else:
                point.distance_from_previous = 0

    @api.depends("iot_device_id", "timestamp")
    def _compute_time_from_previous(self):
        """Compute time from previous point"""
        for point in self:
            if point.iot_device_id and point.timestamp:
                previous = self.search(
                    [
                        ("iot_device_id", "=", point.iot_device_id.id),
                        ("timestamp", "<", point.timestamp),
                    ],
                    order="timestamp desc",
                    limit=1,
                )
                if previous:
                    delta = point.timestamp - previous.timestamp
                    point.time_from_previous = (
                        delta.total_seconds() / 60
                    )  # Convert to minutes
                else:
                    point.time_from_previous = 0
            else:
                point.time_from_previous = 0

    def _prepare_point_data(self):
        """Prepare tracking point data for display/export

        :return: Dictionary with point data
        """
        self.ensure_one()
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "speed": self.speed,
            "heading": self.heading,
            "satellites": self.satellites,
            "accuracy": self.accuracy,
            "ignition": self.ignition,
            "movement": self.movement,
            "odometer": self.odometer,
            "fuel_level": self.fuel_level,
            "device_name": self.iot_device_id.name if self.iot_device_id else None,
            "source": self.source,
        }

    @api.model
    def create_from_iot_data(self, iot_device_id, position_data, session_id=None):
        """Create tracking point from IoT device data

        :param iot_device_id: IoT device ID
        :param position_data: Dictionary with position data
        :param session_id: Optional IoT session ID
        :return: Created tracking point record
        """
        vals = {
            "iot_device_id": iot_device_id,
            "timestamp": position_data.get("timestamp", fields.Datetime.now()),
            "latitude": position_data.get("latitude"),
            "longitude": position_data.get("longitude"),
            "altitude": position_data.get("altitude", 0),
            "speed": position_data.get("speed", 0),
            "heading": position_data.get("heading", 0),
            "satellites": position_data.get("satellites", 0),
            "accuracy": position_data.get("accuracy", 0),
            "ignition": position_data.get("ignition", False),
            "movement": position_data.get("movement", False),
            "source": "iot",
        }

        if session_id:
            vals["iot_session_id"] = session_id

        # Add any additional fields from position_data
        optional_fields = [
            "hdop",
            "pdop",
            "odometer",
            "total_odometer",
            "fuel_level",
            "fuel_consumed",
            "engine_hours",
            "engine_temp",
            "engine_rpm",
            "battery_voltage",
            "external_voltage",
            "gsm_signal",
            "event_type",
            "priority",
        ]

        for field in optional_fields:
            if field in position_data:
                vals[field] = position_data[field]

        return self.create(vals)

    @api.constrains("latitude")
    def _check_latitude(self):
        """Validate latitude is within valid range"""
        for point in self:
            if point.latitude and (point.latitude < -90 or point.latitude > 90):
                raise ValidationError(_("Latitude must be between -90 and 90 degrees"))

    @api.constrains("longitude")
    def _check_longitude(self):
        """Validate longitude is within valid range"""
        for point in self:
            if point.longitude and (point.longitude < -180 or point.longitude > 180):
                raise ValidationError(
                    _("Longitude must be between -180 and 180 degrees")
                )

    @api.constrains("speed")
    def _check_speed(self):
        """Validate speed is reasonable"""
        for point in self:
            if point.speed and point.speed < 0:
                raise ValidationError(_("Speed cannot be negative"))
            if point.speed and point.speed > 300:
                raise ValidationError(_("Speed seems unrealistic (> 300 km/h)"))

    @api.constrains("satellites")
    def _check_satellites(self):
        """Validate satellite count"""
        for point in self:
            if point.satellites and (point.satellites < 0 or point.satellites > 32):
                raise ValidationError(_("Satellite count must be between 0 and 32"))

    @api.constrains("fuel_level", "battery_voltage")
    def _check_percentages(self):
        """Validate percentage and voltage values"""
        for point in self:
            if point.fuel_level and (point.fuel_level < 0 or point.fuel_level > 100):
                raise ValidationError(_("Fuel level must be between 0 and 100%"))
            if point.battery_voltage and point.battery_voltage < 0:
                raise ValidationError(_("Battery voltage cannot be negative"))

    @api.model
    def _cron_cleanup_old_points(self):
        """Cron job to clean old tracking points based on retention policy"""
        _logger.info("Starting GPS tracking points cleanup")

        # Get all GPS configurations with retention settings
        configs = self.env["iot.gps.config"].search(
            [("active", "=", True), ("data_retention_days", ">", 0)]
        )

        for config in configs:
            # Find devices using this config
            devices = self.env["iot.device"].search([("gps_config_id", "=", config.id)])

            if devices:
                # Calculate cutoff date
                from datetime import datetime, timedelta

                cutoff_date = datetime.now() - timedelta(
                    days=config.data_retention_days
                )

                # Find and delete old points
                old_points = self.search(
                    [
                        ("iot_device_id", "in", devices.ids),
                        ("timestamp", "<", cutoff_date),
                    ]
                )

                if old_points:
                    count = len(old_points)
                    old_points.unlink()
                    _logger.info(
                        f"Deleted {count} old tracking points for config {config.name}"
                    )

        _logger.info("GPS tracking points cleanup completed")
