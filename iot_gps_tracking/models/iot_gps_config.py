from odoo import api, fields, models


class IoTGpsConfig(models.Model):
    _name = "iot.gps.config"
    _description = "IoT GPS Device Configuration"
    _order = "name"

    name = fields.Char(
        string="Configuration Name",
        required=True,
        help="Name for this GPS configuration profile",
    )

    description = fields.Text(
        string="Description",
        help="Description of this configuration profile",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=False,
        default=lambda self: self.env.company,
        help="Company that owns this configuration. Leave empty for multi-company",
    )

    # Device settings
    manufacturer = fields.Char(
        string="Manufacturer",
        help="GPS device manufacturer",
    )

    model = fields.Char(
        string="Model",
        help="GPS device model",
    )

    protocol = fields.Selection(
        [
            ("teltonika", "Teltonika"),
            ("queclink", "Queclink"),
            ("concox", "Concox"),
            ("meitrack", "Meitrack"),
            ("generic", "Generic"),
        ],
        string="Protocol",
        default="generic",
        help="GPS communication protocol",
    )

    # Update settings
    update_interval = fields.Integer(
        string="Update Interval (seconds)",
        default=30,
        help="How often the device should report position",
    )

    stationary_interval = fields.Integer(
        string="Stationary Interval (seconds)",
        default=300,
        help="Update interval when device is stationary",
    )

    # Motion detection
    motion_threshold_speed = fields.Float(
        string="Motion Threshold Speed (km/h)",
        default=5.0,
        help="Minimum speed to consider device as moving",
    )

    motion_threshold_distance = fields.Float(
        string="Motion Threshold Distance (m)",
        default=50.0,
        help="Minimum distance to consider device as moving",
    )

    # Data collection
    collect_telemetry = fields.Boolean(
        string="Collect Telemetry",
        default=True,
        help="Collect vehicle telemetry data (fuel, engine, etc.)",
    )

    collect_sensors = fields.Boolean(
        string="Collect Sensors",
        default=True,
        help="Collect sensor data (temperature, voltage, etc.)",
    )

    # Alerts
    enable_overspeeding_alert = fields.Boolean(
        string="Enable Overspeeding Alert",
        help="Alert when device exceeds speed limit",
    )

    speed_limit = fields.Float(
        string="Speed Limit (km/h)",
        default=120.0,
        help="Maximum allowed speed",
    )

    enable_idle_alert = fields.Boolean(
        string="Enable Idle Alert",
        help="Alert when device is idle for too long",
    )

    idle_threshold = fields.Integer(
        string="Idle Threshold (minutes)",
        default=30,
        help="Time before idle alert is triggered",
    )

    # Battery monitoring
    enable_battery_alert = fields.Boolean(
        string="Enable Battery Alert",
        help="Alert on low battery",
    )

    battery_threshold = fields.Float(
        string="Battery Threshold (%)",
        default=20.0,
        help="Battery level threshold for alerts",
    )

    # Data retention
    retention_days = fields.Integer(
        string="Data Retention (days)",
        default=90,
        help="How long to keep tracking data",
    )

    # Advanced settings
    min_satellites = fields.Integer(
        string="Minimum Satellites",
        default=4,
        help="Minimum satellites for valid GPS fix",
    )

    max_hdop = fields.Float(
        string="Maximum HDOP",
        default=5.0,
        help="Maximum HDOP for valid GPS fix",
    )

    active = fields.Boolean(
        string="Active",
        default=True,
        index=True,  # Index for filtering active configs
        help="Whether this configuration is active",
    )

    # Related devices
    device_ids = fields.One2many(
        "iot.device",
        "gps_config_id",
        string="Devices",
        help="Devices using this configuration",
    )

    device_count = fields.Integer(
        string="Device Count",
        compute="_compute_device_count",
        help="Number of devices using this configuration",
    )

    @api.depends("device_ids")
    def _compute_device_count(self):
        for config in self:
            config.device_count = len(config.device_ids)

    def action_view_devices(self):
        """View devices using this configuration"""
        self.ensure_one()
        return {
            "name": f"Devices - {self.name}",
            "type": "ir.actions.act_window",
            "res_model": "iot.device",
            "view_mode": "tree,form",
            "domain": [("gps_config_id", "=", self.id)],
            "context": {
                "default_gps_config_id": self.id,
                "default_type": "gps_tracker",
            },
        }
