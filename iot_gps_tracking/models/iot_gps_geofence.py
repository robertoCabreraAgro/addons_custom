import json

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class IoTGpsGeofence(models.Model):
    _name = "iot.gps.geofence"
    _description = "IoT GPS Geofence"
    _order = "name"

    name = fields.Char(
        string="Name",
        required=True,
        help="Geofence name",
    )

    description = fields.Text(
        string="Description",
        help="Geofence description",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=False,
        default=lambda self: self.env.company,
        help="Company that owns this geofence. Leave empty for multi-company",
    )

    # Geofence shape
    geofence_type = fields.Selection(
        [
            ("circle", "Circle"),
            ("polygon", "Polygon"),
            ("rectangle", "Rectangle"),
        ],
        string="Type",
        default="circle",
        required=True,
        help="Geofence shape type",
    )

    # Circle parameters
    center_latitude = fields.Float(
        string="Center Latitude",
        digits=(10, 7),
        help="Center latitude for circle geofence",
    )

    center_longitude = fields.Float(
        string="Center Longitude",
        digits=(10, 7),
        help="Center longitude for circle geofence",
    )

    radius = fields.Float(
        string="Radius (m)",
        default=100.0,
        help="Radius in meters for circle geofence",
    )

    # Polygon/Rectangle parameters
    polygon_points = fields.Text(
        string="Polygon Points",
        help="JSON array of [lat, lon] points for polygon geofence",
    )

    the_geom = fields.GeoMultiPolygon(
        string="Geometry",
        compute="_compute_the_geom",
        store=True,
        help="Geographic geometry for map display",
    )

    # Alert settings
    alert_on_enter = fields.Boolean(
        string="Alert on Enter",
        default=True,
        help="Send alert when device enters geofence",
    )

    alert_on_exit = fields.Boolean(
        string="Alert on Exit",
        default=True,
        help="Send alert when device exits geofence",
    )

    alert_on_dwell = fields.Boolean(
        string="Alert on Dwell",
        help="Send alert when device stays in geofence too long",
    )

    dwell_time = fields.Integer(
        string="Dwell Time (minutes)",
        default=30,
        help="Time before dwell alert is triggered",
    )

    # Schedule
    active = fields.Boolean(
        string="Active",
        default=True,
        index=True,  # Index for filtering active geofences
        help="Whether this geofence is active",
    )

    schedule_type = fields.Selection(
        [
            ("always", "Always"),
            ("business_hours", "Business Hours"),
            ("custom", "Custom Schedule"),
        ],
        string="Schedule",
        default="always",
        help="When this geofence is active",
    )

    schedule_weekdays = fields.Selection(
        [
            ("0", "Monday"),
            ("1", "Tuesday"),
            ("2", "Wednesday"),
            ("3", "Thursday"),
            ("4", "Friday"),
            ("5", "Saturday"),
            ("6", "Sunday"),
        ],
        string="Active Days",
        help="Days when geofence is active (for custom schedule)",
    )

    schedule_time_from = fields.Float(
        string="Active From",
        help="Start time (24h format, e.g., 8.5 for 8:30)",
    )

    schedule_time_to = fields.Float(
        string="Active To",
        help="End time (24h format, e.g., 17.5 for 17:30)",
    )

    # Color for display
    color = fields.Char(
        string="Color",
        default="#FF0000",
        help="Color for map display",
    )

    # Related devices
    device_ids = fields.Many2many(
        "iot.device",
        "iot_device_geofence_rel",
        "geofence_id",
        "device_id",
        string="Monitored Devices",
        domain=[("type", "=", "gps_tracker")],
        help="Devices monitored by this geofence",
    )

    device_count = fields.Integer(
        string="Device Count",
        compute="_compute_device_count",
        help="Number of devices monitored",
    )

    # Current devices inside
    devices_inside_ids = fields.Many2many(
        "iot.device",
        "iot_device_inside_geofence_rel",
        "geofence_id",
        "device_id",
        string="Devices Inside",
        compute="_compute_devices_inside",
        help="Devices currently inside this geofence",
    )

    devices_inside_count = fields.Integer(
        string="Devices Inside Count",
        compute="_compute_devices_inside",
        help="Number of devices currently inside",
    )

    @api.depends(
        "geofence_type",
        "center_latitude",
        "center_longitude",
        "radius",
        "polygon_points",
    )
    def _compute_the_geom(self):
        """Compute geometry from geofence parameters"""
        for geofence in self:
            if (
                geofence.geofence_type == "circle"
                and geofence.center_latitude
                and geofence.center_longitude
            ):
                # Create a circle approximation as polygon
                # This is simplified - a proper implementation would create a multi-point polygon
                geofence.the_geom = f"MULTIPOLYGON(((POINT({geofence.center_longitude} {geofence.center_latitude}))))"
            elif (
                geofence.geofence_type in ["polygon", "rectangle"]
                and geofence.polygon_points
            ):
                try:
                    points = json.loads(geofence.polygon_points)
                    if points and len(points) >= 3:
                        # Create WKT polygon string
                        wkt_points = " ".join([f"{p[1]} {p[0]}" for p in points])
                        # Close the polygon by adding first point at the end
                        wkt_points += f" {points[0][1]} {points[0][0]}"
                        geofence.the_geom = f"MULTIPOLYGON((({wkt_points})))"
                    else:
                        geofence.the_geom = False
                except (json.JSONDecodeError, IndexError):
                    geofence.the_geom = False
            else:
                geofence.the_geom = False

    @api.depends("device_ids")
    def _compute_device_count(self):
        for geofence in self:
            geofence.device_count = len(geofence.device_ids)

    @api.depends(
        "device_ids", "device_ids.gps_last_latitude", "device_ids.gps_last_longitude"
    )
    def _compute_devices_inside(self):
        """Compute which devices are currently inside the geofence"""
        for geofence in self:
            inside_devices = self.env["iot.device"]
            for device in geofence.device_ids:
                if device.gps_last_latitude and device.gps_last_longitude:
                    if geofence._is_point_inside(
                        device.gps_last_latitude, device.gps_last_longitude
                    ):
                        inside_devices |= device
            geofence.devices_inside_ids = inside_devices
            geofence.devices_inside_count = len(inside_devices)

    def _is_point_inside(self, latitude, longitude):
        """Check if a point is inside the geofence

        :param latitude: Point latitude
        :param longitude: Point longitude
        :return: True if point is inside geofence
        """
        self.ensure_one()

        if self.geofence_type == "circle":
            if not (self.center_latitude and self.center_longitude):
                return False

            # Calculate distance using Haversine formula
            from math import radians, cos, sin, asin, sqrt

            lon1, lat1 = radians(self.center_longitude), radians(self.center_latitude)
            lon2, lat2 = radians(longitude), radians(latitude)

            dlon = lon2 - lon1
            dlat = lat2 - lat1
            a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
            c = 2 * asin(sqrt(a))
            distance_m = 6371000 * c  # Radius of earth in meters

            return distance_m <= self.radius

        elif self.geofence_type in ["polygon", "rectangle"]:
            if not self.polygon_points:
                return False

            try:
                points = json.loads(self.polygon_points)
                if not points or len(points) < 3:
                    return False

                # Point in polygon algorithm (ray casting)
                inside = False
                p1x, p1y = points[0]
                for i in range(1, len(points) + 1):
                    p2x, p2y = points[i % len(points)]
                    if latitude > min(p1y, p2y):
                        if latitude <= max(p1y, p2y):
                            if longitude <= max(p1x, p2x):
                                if p1y != p2y:
                                    xinters = (latitude - p1y) * (p2x - p1x) / (
                                        p2y - p1y
                                    ) + p1x
                                if p1x == p2x or longitude <= xinters:
                                    inside = not inside
                    p1x, p1y = p2x, p2y

                return inside

            except (json.JSONDecodeError, IndexError):
                return False

        return False

    @api.constrains(
        "geofence_type",
        "center_latitude",
        "center_longitude",
        "radius",
        "polygon_points",
    )
    def _check_geofence_data(self):
        """Validate geofence data"""
        for geofence in self:
            if geofence.geofence_type == "circle":
                if not (geofence.center_latitude and geofence.center_longitude):
                    raise ValidationError(
                        _("Circle geofence requires center coordinates")
                    )
                if geofence.radius <= 0:
                    raise ValidationError(_("Circle radius must be positive"))
                if geofence.radius > 100000:
                    raise ValidationError(_("Circle radius cannot exceed 100km"))
                if abs(geofence.center_latitude) > 90:
                    raise ValidationError(_("Latitude must be between -90 and 90"))
                if abs(geofence.center_longitude) > 180:
                    raise ValidationError(_("Longitude must be between -180 and 180"))
            elif geofence.geofence_type in ["polygon", "rectangle"]:
                if not geofence.polygon_points:
                    raise ValidationError(_("Polygon geofence requires points"))
                try:
                    points = json.loads(geofence.polygon_points)
                    if not isinstance(points, list) or len(points) < 3:
                        raise ValidationError(_("Polygon requires at least 3 points"))
                except json.JSONDecodeError:
                    raise ValidationError(_("Invalid polygon points format"))

    def action_view_devices(self):
        """View devices monitored by this geofence"""
        self.ensure_one()
        return {
            "name": f"Devices - {self.name}",
            "type": "ir.actions.act_window",
            "res_model": "iot.device",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.device_ids.ids)],
            "context": {
                "default_type": "gps_tracker",
            },
        }

    def action_view_devices_inside(self):
        """View devices currently inside this geofence"""
        self.ensure_one()
        return {
            "name": f"Devices Inside - {self.name}",
            "type": "ir.actions.act_window",
            "res_model": "iot.device",
            "view_mode": "tree,form,map",
            "domain": [("id", "in", self.devices_inside_ids.ids)],
        }

    def check_device_position(self, device_id, latitude, longitude):
        """Check if a device position triggers any geofence alerts

        :param device_id: IoT device ID
        :param latitude: Device latitude
        :param longitude: Device longitude
        :return: List of triggered alerts
        """
        self.ensure_one()

        device = self.env["iot.device"].browse(device_id)
        if device not in self.device_ids:
            return []

        alerts = []
        is_inside = self._is_point_inside(latitude, longitude)
        was_inside = device in self.devices_inside_ids

        # Check enter/exit alerts
        if is_inside and not was_inside and self.alert_on_enter:
            alerts.append(
                {
                    "type": "geofence_enter",
                    "geofence_id": self.id,
                    "geofence_name": self.name,
                    "device_id": device_id,
                    "device_name": device.name,
                    "timestamp": fields.Datetime.now(),
                }
            )
        elif not is_inside and was_inside and self.alert_on_exit:
            alerts.append(
                {
                    "type": "geofence_exit",
                    "geofence_id": self.id,
                    "geofence_name": self.name,
                    "device_id": device_id,
                    "device_name": device.name,
                    "timestamp": fields.Datetime.now(),
                }
            )

        return alerts

    @api.model
    def _cron_process_geofence_alerts(self):
        """Cron job to process geofence alerts for all active geofences"""
        from datetime import datetime, time

        _logger.info("Processing geofence alerts")

        # Get current time for schedule checking
        now = datetime.now()
        current_time = now.time()
        current_weekday = str(now.weekday())

        # Find active geofences
        geofences = self.search([("active", "=", True)])

        for geofence in geofences:
            # Check if geofence is active based on schedule
            is_active = False

            if geofence.schedule_type == "always":
                is_active = True
            elif geofence.schedule_type == "business_hours":
                # Check if current time is within business hours (8 AM - 6 PM)
                if (
                    time(8, 0) <= current_time <= time(18, 0)
                    and int(current_weekday) < 5
                ):
                    is_active = True
            elif geofence.schedule_type == "custom":
                # Check custom schedule
                if geofence.schedule_time_from and geofence.schedule_time_to:
                    from_hour = int(geofence.schedule_time_from)
                    from_minute = int((geofence.schedule_time_from % 1) * 60)
                    to_hour = int(geofence.schedule_time_to)
                    to_minute = int((geofence.schedule_time_to % 1) * 60)

                    if (
                        time(from_hour, from_minute)
                        <= current_time
                        <= time(to_hour, to_minute)
                    ):
                        if (
                            not geofence.schedule_weekdays
                            or current_weekday in geofence.schedule_weekdays
                        ):
                            is_active = True

            if is_active:
                # Check all monitored devices
                for device in geofence.device_ids:
                    if device.gps_last_latitude and device.gps_last_longitude:
                        alerts = geofence.check_device_position(
                            device.id,
                            device.gps_last_latitude,
                            device.gps_last_longitude,
                        )

                        # Process any generated alerts
                        for alert in alerts:
                            _logger.info(
                                f"Geofence alert: {alert['type']} for device {alert['device_name']} in {alert['geofence_name']}"
                            )
                            # TODO: Send notifications based on alert type

        _logger.info("Geofence alert processing completed")
