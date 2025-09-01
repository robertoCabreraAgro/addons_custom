from pyproj import Transformer

from odoo import api, fields, models


class GpsTrackingPoint(models.Model):
    _name = "gps.tracking.point"
    _description = "GPS Tracking Point"
    _order = "timestamp desc"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    device_id = fields.Many2one(
        comodel_name="gps.tracking.device",
        string="Device",
        required=True,
        ondelete="cascade",
    )
    asset_id = fields.Many2one(
        comodel_name="stock.lot",
        compute="_compute_asset_id",
        store=True,
        readonly=True,
        string="Asset",
    )
    driver_id = fields.Many2one(
        related="asset_id.operator_id",
        store=True,
        readonly=True,
    )
    timestamp = fields.Datetime(string="Timestamp", required=True)
    priority = fields.Integer(string="Priority")
    angle = fields.Float(string="Angle")
    altitude = fields.Float(string="Altitude")
    latitude = fields.Float(string="Latitude", digits=(16, 7))
    longitude = fields.Float(string="Longitude", digits=(16, 7))
    the_point = fields.GeoPoint(
        string="Position",
        srid=3857,
        compute="_compute_the_point",
        store=True,
    )
    ignition = fields.Integer(string="Ignition")
    movement = fields.Integer(string="Movement")
    speed = fields.Float(string="Speed")
    wheel_speed = fields.Float(string="Wheel Speed")
    parking_brake_state = fields.Integer(string="Parking Brake State")
    central_lock = fields.Integer(string="Central Lock")
    gsm_signal = fields.Integer(string="GSM Signal")
    active_gsm_operator = fields.Integer(string="Active GSM Operator")
    satellites = fields.Integer(string="Satellites")
    gnss_status = fields.Integer(string="GNSS Status")
    gnss_pdop = fields.Float(string="GNSS PDOP", digits=(16, 2))
    gnss_hdop = fields.Float(string="GNSS HDOP", digits=(16, 2))
    sleep_mode = fields.Integer(string="Sleep Mode")
    external_voltage = fields.Float(string="External Voltage", digits=(16, 3))
    battery_voltage = fields.Float(string="Battery Voltage", digits=(16, 3))
    battery_current = fields.Float(string="Battery Current", digits=(16, 3))
    fuel_level = fields.Integer(string="Fuel Level")
    fuel_level_l = fields.Float(string="Fuel Level (L)", digits=(16, 2))
    fuel_consumed_counted = fields.Float(string="Fuel Consumed Counted", digits=(16, 2))
    engine_speed_rpm = fields.Integer(string="Engine Speed (RPM)")
    engine_temperature = fields.Float(string="Engine Temperature", digits=(16, 2))
    engine_total_hours = fields.Float(string="Engine Total Hours", digits=(16, 2))
    engine_total_hours_counted = fields.Float(
        string="Engine Total Hours", digits=(16, 2)
    )
    isf_check_engine_indicator = fields.Integer(string="ISF Check Engine Indicator")
    iccid1 = fields.Char(string="ICCID1")
    odometer = fields.Integer(string="Odometer")
    total_odometer = fields.Integer(string="Total Odometer")
    real_odometer = fields.Float(
        string="Real Odometer",
        digits=(16, 2),
        compute="_compute_real_odometer",
        store=True,
        help="Corrected odometer reading based on device configuration",
    )
    control_state_flags = fields.Char(
        string="Control State Flags",
        help="This is an hexadecimal flag to check vehicle state",
    )
    event_id = fields.Integer(string="Event ID")
    event_type = fields.Char(string="Event Type")
    auto_geofence = fields.Integer(string="Auto Geofence")

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    @api.depends("device_id")
    def _compute_asset_id(self):
        for point in self:
            point.asset_id = (
                point.device_id.asset_ids[0] if point.device_id.asset_ids else False
            )

    @api.depends("device_id")
    def _compute_real_odometer(self):
        """Calculate real odometer reading based on device configuration"""
        for point in self:
            config = point.device_id.config_id
            # Use odometer or total_odometer based on configuration
            if config.reports_odometer:
                raw_odometer = point.odometer or 0
            else:
                raw_odometer = point.total_odometer or 0

            point.real_odometer = config.get_corrected_odometer(raw_odometer)

    @api.depends("latitude", "longitude")
    def _compute_the_point(self):
        transformer = Transformer.from_crs(4326, 3857, always_xy=True)
        for point in self:
            if point.latitude and point.longitude and not point.the_point:
                x, y = transformer.transform(point.longitude, point.latitude)
                point.the_point = f"POINT({x} {y})"
