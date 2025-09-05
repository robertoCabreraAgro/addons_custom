from datetime import timedelta
from pytz import utc

from odoo import api, fields, models


class GpsTrackingDevice(models.Model):
    _name = "gps.tracking.device"
    _description = "GPS Tracking Device"
    _rec_name = "imei"

    INACTIVITY_INACTIVE_HOURS = 1.5
    INACTIVITY_WARNING_HOURS = 1.0

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    imei = fields.Char(
        string="IMEI",
        required=True,
    )
    config_id = fields.Many2one(
        comodel_name="gps.tracking.config",
        string="GPS Configuration",
        required=True,
        help="Configuration for interpreting GPS device data",
    )
    asset_ids = fields.One2many(
        comodel_name="stock.lot",
        inverse_name="gps_device_id",
    )
    asset_id = fields.Many2one(
        comodel_name="stock.lot",
        string="Vehiculo",
        compute="_compute_asset_id",
        store=True,
        readonly=True,
        help="Main asset assigned to this GPS device",
    )
    tracking_point_ids = fields.One2many(
        comodel_name="gps.tracking.point",
        inverse_name="device_id",
        string="Tracking Points",
    )
    allowed_tracking_point_ids = fields.One2many(
        comodel_name="gps.tracking.point",
        string="Allowed Tracking Points",
        compute="_compute_allowed_tracking_point_ids",
    )
    # Last point related fields
    last_point_id = fields.Many2one(
        comodel_name="gps.tracking.point",
        string="Last Tracking Point",
    )
    satellites = fields.Integer(
        related="last_point_id.satellites",
    )
    timestamp = fields.Datetime(
        related="last_point_id.timestamp",
    )
    altitude = fields.Float(
        related="last_point_id.altitude",
    )
    the_point = fields.GeoPoint(
        related="last_point_id.the_point",
        string="Current Position",
    )
    ignition = fields.Integer(
        related="last_point_id.ignition",
    )
    movement = fields.Integer(
        related="last_point_id.movement",
    )
    speed = fields.Float(
        related="last_point_id.speed",
    )
    odometer = fields.Integer(
        related="last_point_id.odometer",
        string="Odometer",
    )
    total_odometer = fields.Integer(
        related="last_point_id.total_odometer",
    )
    real_odometer = fields.Float(
        related="last_point_id.real_odometer",
    )

    color = fields.Selection(
        selection=[
            ("#FF0000", "Rojo"),
            ("#0000FF", "Azul"),
            ("#008000", "Verde"),
            ("#FFA500", "Naranja"),
            ("#800080", "Morado"),
            ("#000000", "Negro"),
        ],
        string="Color of the Route",
        default="#FF0000",
    )
    inactivity_state = fields.Selection(
        selection=[
            ("active", "Active"),
            ("warning", "Warning - Inactive Soon"),
            ("inactive_alert", "Inactive Alert"),
            ("unknown", "Unknown Status"),
        ],
        string="Inactivity State",
        compute="_compute_inactivity_state",
        store=True,
    )
    last_activity_hours = fields.Float(
        string="Hours Since Last Activity",
        compute="_compute_inactivity_state",
        store=True,
        help="Number of hours since the device last reported",
    )
    private = fields.Boolean(
        default=False,
        groups="gps_tracking.group_gps_tracking_private",
        help="If checked, only users with specific access rights can see this device",
    )

    # ------------------------------------------------------------
    # CONSTRAINTS
    # ------------------------------------------------------------

    _unique_code = models.Constraint(
        "unique (imei)",
        "This IMEI already exists",
    )

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    @api.depends("asset_ids")
    def _compute_asset_id(self):
        for device in self:
            device.asset_id = device.asset_ids[:1] if device.asset_ids else False

    @api.depends("tracking_point_ids")
    def _compute_allowed_tracking_point_ids(self):
        now = fields.Datetime.now()
        last_week = now - timedelta(days=7)
        for device in self:
            device.allowed_tracking_point_ids = self.env["gps.tracking.point"].search(
                [("device_id", "=", device.id), ("timestamp", ">=", last_week)],
                order="timestamp desc",
            )

    @api.depends("timestamp")
    def _compute_inactivity_state(self):
        """
        Compute device inactivity state based on last report timestamp.

        States:
        - active: Device reported within warning threshold
        - warning: Device approaching inactivity threshold (optional)
        - inactive_alert: Device exceeded inactivity threshold
        - unknown: No timestamp available

        The thresholds can be configured via system parameters or model constants.
        """
        inactive_threshold = self._get_inactivity_threshold()
        warning_threshold = self._get_warning_threshold()
        now_utc = fields.Datetime.now()
        for device in self:
            try:
                device._set_device_inactivity_state(
                    now_utc, inactive_threshold, warning_threshold
                )
            except Exception as e:
                device.inactivity_state = "unknown"
                device.last_activity_hours = 0.0

    # ------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------

    def get_fuel_level_percentage(self, target_datetime):
        """Get fuel level at specific datetime based on configuration.

        Args:
            target_datetime (datetime): Target datetime for fuel reading

        Returns:
            dict: Dictionary with 'percentage' and 'liters' keys, or False if not available
        """
        self.ensure_one()
        target_datetime = target_datetime or fields.Datetime.now()
        # Find the closest tracking point to the target datetime
        point = self.env["gps.tracking.point"].search(
            [("device_id", "=", self.id), ("timestamp", "<=", target_datetime)],
            order="timestamp desc",
            limit=1,
        )
        if not point:
            return False

        fuel_percentage = point.fuel_level
        if fuel_percentage:
            return fuel_percentage

        # If device provides volume, convert to percentage
        fuel_deciliters = point.fuel_level_l
        if fuel_deciliters and self.asset_ids[0].fuel_tank_capacity:
            fuel_percentage = (
                (fuel_deciliters * 10) / self.config_id.fuel_tank_capacity
            ) * 100
            return fuel_percentage or 0.0

    def get_odometer(self, target_datetime=False):
        """Get odometer reading at specific datetime using real_odometer field.

        Args:
            target_datetime (datetime): Target datetime for odometer reading

        Returns:
            float: Odometer value from real_odometer field or False if not available
        """
        self.ensure_one()
        target_datetime = target_datetime or fields.Datetime.now()
        # Find the closest tracking point to the target datetime
        point = self.env["gps.tracking.point"].search(
            [("device_id", "=", self.id), ("timestamp", "<=", target_datetime)],
            order="timestamp desc",
            limit=1,
        )
        if not point:
            return False

        return point.real_odometer

    @api.model
    def _get_inactivity_threshold(self):
        """
        Get inactivity threshold from configuration.
        Can be overridden to use system parameters or company-specific settings.

        :return: timedelta object representing the threshold
        """
        param_obj = self.env["ir.config_parameter"].sudo()
        hours = float(
            param_obj.get_param(
                "gps_tracking.INACTIVITY_INACTIVE_HOURS",
                default=self.INACTIVITY_INACTIVE_HOURS,
            )
        )
        return timedelta(hours=hours)

    @api.model
    def _get_warning_threshold(self):
        """
        Get warning threshold from configuration.

        :return: timedelta object or None if warning state is disabled
        """
        # Option to disable warning state
        param_obj = self.env["ir.config_parameter"].sudo()
        warning_enabled = param_obj.get_param(
            "gps_tracking.inactivity_warning_enabled", default="True"
        )

        if warning_enabled.lower() == "false":
            return None

        hours = float(
            param_obj.get_param(
                "gps_tracking.inactivity_warning_hours",
                default=self.INACTIVITY_WARNING_HOURS,
            )
        )
        return timedelta(hours=hours)

    @api.model
    def get_inactivity_statistics(self):
        """
        Get statistics about device inactivity states.
        Useful for dashboards and reports.

        :return: Dictionary with statistics
        """
        domain = []
        if self._context.get("active_ids"):
            domain = [("id", "in", self._context["active_ids"])]

        devices = self.search(domain)

        stats = {
            "total": len(devices),
            "active": len(devices.filtered(lambda d: d.inactivity_state == "active")),
            "warning": len(devices.filtered(lambda d: d.inactivity_state == "warning")),
            "inactive": len(
                devices.filtered(lambda d: d.inactivity_state == "inactive_alert")
            ),
            "unknown": len(devices.filtered(lambda d: d.inactivity_state == "unknown")),
            "avg_hours_inactive": (
                sum(devices.mapped("last_activity_hours")) / len(devices)
                if devices
                else 0
            ),
        }

        return stats

    def _send_inactivity_alerts(self, devices):
        """
        Send alerts for inactive devices.
        Override this method to implement custom alert logic.

        :param devices: Recordset of inactive devices
        """
        for device in devices:
            # Check if alert was already sent recently
            if self._should_send_alert(device):
                # Implement your alert logic here
                pass

    def _set_device_inactivity_state(
        self, now_utc, inactive_threshold, warning_threshold
    ):
        """
        Set the inactivity state for a single device.

        :param now_utc: Current UTC datetime
        :param inactive_threshold: Timedelta for inactive alert
        :param warning_threshold: Timedelta for warning state
        """
        if not self.timestamp:
            self.inactivity_state = "unknown"
            self.last_activity_hours = 0.0
            return

        # Ensure timestamp is timezone-aware (Odoo stores as UTC)
        last_report_utc = fields.Datetime.to_datetime(self.timestamp)
        if not last_report_utc.tzinfo:
            last_report_utc = last_report_utc.replace(tzinfo=utc)

        # Calculate duration since last report
        inactive_duration = now_utc - last_report_utc
        hours_inactive = inactive_duration.total_seconds() / 3600
        self.last_activity_hours = round(hours_inactive, 2)

        # Determine state based on thresholds
        if inactive_duration >= inactive_threshold:
            self.inactivity_state = "inactive_alert"
        elif warning_threshold and inactive_duration >= warning_threshold:
            self.inactivity_state = "warning"
        else:
            self.inactivity_state = "active"

    # ------------------------------------------------------------
    # VALIDATIONS
    # ------------------------------------------------------------

    @api.model
    def check_and_alert_inactive_devices(self):
        """
        Cron job method to check for inactive devices and send alerts.
        Can be called from a scheduled action.
        """
        inactive_devices = self.search([("inactivity_state", "=", "inactive_alert")])

        if inactive_devices:
            # Trigger notifications, emails, etc.
            self._send_inactivity_alerts(inactive_devices)

        return True

    def _should_send_alert(self, device):
        """
        Check if an alert should be sent for this device.
        Prevents alert spam by checking last alert time.

        :param device: Device record
        :return: Boolean indicating if alert should be sent
        """
        # Implement logic to prevent duplicate alerts
        # e.g., check last alert timestamp, alert frequency settings, etc.
        return True
