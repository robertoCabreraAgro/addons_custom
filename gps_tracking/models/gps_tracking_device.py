import logging
from datetime import datetime, timedelta
from odoo import api, fields, models
from pyproj import Transformer
from pytz import timezone, utc

_logger = logging.getLogger(__name__)


class GpsTrackingDevice(models.Model):
    _name = "gps.tracking.device"
    _description = "GPS Tracking Device"
    _rec_name = "imei"

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
    vehicle_id = fields.Many2one(
        comodel_name="fleet.vehicle",
        string="Vehícle",
        help="Vehículo asociado al dispositivo GPS",
    )
    license_plate = fields.Char(
        related="vehicle_id.license_plate",
        store=True,
        string="Plate",
    )
    driver_name = fields.Char(
        string="Driver",
        compute="_compute_driver_name",
        store=True,
    )
    location = fields.Char(
        related="vehicle_id.location",
        store=True,
        string="Location",
    )
    model_id = fields.Many2one(
        related="vehicle_id.model_id",
        store=True,
        comodel_name="fleet.vehicle.model",
        string="Model",
    )
    allowed_tracking_point = fields.One2many(
        comodel_name="gps.tracking.point",
        compute="_compute_allowed_tracking_point",
        string="Allowed Tracking Points",
    )
    tracking_points = fields.One2many(
        comodel_name="gps.tracking.point",
        inverse_name="device_id",
        string="Tracking Points",
    )
    last_point_id = fields.Many2one(
        comodel_name="gps.tracking.point",
        string="Last Tracking Point",
    )
    speed = fields.Float(
        related="last_point_id.speed",
        store=True,
        string="Speed",
    )
    satellite = fields.Integer(
        related="last_point_id.satellites",
        store=True,
        string="Satélites",
    )
    timestamp = fields.Datetime(
        related="last_point_id.timestamp",
        store=True,
        string="Timestamp",
    )
    altitude = fields.Float(
        related="last_point_id.altitude",
        store=True,
        string="Altitude",
    )
    address = fields.Char(
        related="last_point_id.address",
        store=True,
        string="Address",
    )
    the_point = fields.GeoPoint(
        string="Current Position",
        related="last_point_id.the_point",
        store=True,
    )
    history_route = fields.GeoLine(
        string="History Route",
    )
    gsm_signal = fields.Integer(
        related="last_point_id.gsm_signal",
        store=True,
        string="GSM Signal",
    )
    ignition = fields.Integer(
        related="last_point_id.ignition",
        store=True,
        string="Ignition",
    )
    movement = fields.Integer(
        related="last_point_id.movement",
        store=True,
        string="Movement",
    )
    total_odometer = fields.Integer(
        related="last_point_id.total_odometer", store=True, string="Total Odometer"
    )
    odometer = fields.Integer(
        related="last_point_id.odometer", store=True, string="Odometer"
    )
    real_odometer = fields.Float(
        related="last_point_id.real_odometer", store=True, string="Real Odometer"
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
        string="Color de Recorrido",
        default="#FF0000",
    )
    private = fields.Boolean(
        default=False,
        groups="gps_tracking.group_gps_tracking_private",
        help="If checked, only users with specific access rights can see this device",
    )
    inactivity_status = fields.Selection(
        selection=[
            ("active", "Activo"),
            ("inactive_alert", "Inactivo"),
        ],
        string="Estado de Inactividad",
        compute="_compute_inactivity_status",
        store=False,
    )

    _unique_code = models.Constraint(
        "unique (imei)",
        "This IMEI already exists",
    )

    def _compute_inactivity_status(self):
        """
        Calcula el estado de inactividad de un dispositivo basado en el último reporte.
        Un dispositivo se considera inactivo si no ha reportado en las últimas 2 horas.
        """
        now_utc = datetime.now(utc)

        for device in self:
            if not device.timestamp:
                device.inactivity_status = "inactive_alert"
                continue

            last_report_utc = fields.Datetime.to_datetime(device.timestamp).replace(
                tzinfo=utc
            )

            inactive_duration = now_utc - last_report_utc

            if inactive_duration >= timedelta(hours=2):
                device.inactivity_status = "inactive_alert"
            else:
                device.inactivity_status = "active"

    @api.depends("tracking_points")
    def _compute_allowed_tracking_point(self):
        now = datetime.now()
        last_week = now - timedelta(days=7)

        for device in self:
            device.allowed_tracking_point = self.env["gps.tracking.point"].search(
                [("device_id", "=", device.id), ("timestamp", ">=", last_week)],
                order="timestamp desc",
            )

    @api.depends("vehicle_id.driver_id", "vehicle_id.location")
    def _compute_driver_name(self):
        for device in self:
            device.driver_name = (
                device.vehicle_id.driver_id.name if device.vehicle_id.driver_id else ""
            )

    @api.depends("tracking_points.timestamp")
    def _compute_last_point(self):
        for device in self:
            last_point = device.tracking_points.sorted(
                key=lambda p: p.timestamp, reverse=True
            )[:1]
            device.last_point_id = last_point.id if last_point else False

            if last_point:
                _logger.info(
                    f"Dispositivo {device.id}: Último punto actualizado a {last_point.id} con timestamp {last_point.timestamp}"
                )
            else:
                _logger.warning(
                    f"Dispositivo {device.id}: No se encontraron puntos para actualizar el último punto."
                )

    @api.depends("tracking_points.latitude", "tracking_points.longitude")
    def _compute_history_route(self):
        transformer = Transformer.from_crs(4326, 3857, always_xy=True)
        for device in self:
            points = device.tracking_points.sorted("timestamp")
            coords = []
            for point in points:
                if point.latitude and point.longitude:
                    x, y = transformer.transform(point.longitude, point.latitude)
                    coords.append(f"{x} {y}")
            if len(coords) > 1:
                device.history_route = f"LINESTRING({', '.join(coords)})"
            else:
                device.history_route = False

    @api.constrains("vehicle_id", "config_id")
    def _check_vehicle_config_association(self):
        """Validate that device has configuration when associated with vehicle."""
        for device in self:
            if device.vehicle_id and not device.config_id:
                raise ValueError(
                    "GPS device must have a configuration assigned before "
                    "associating it with a vehicle."
                )

    def get_fuel_at(self, target_datetime):
        """Get fuel level at specific datetime based on configuration.

        Args:
            target_datetime (datetime): Target datetime for fuel reading

        Returns:
            dict: Dictionary with 'percentage' and 'liters' keys, or False if not available
        """
        self.ensure_one()
        if not self.config_id:
            raise ValueError("Device must have a configuration to get fuel reading")

        # Find the closest tracking point to the target datetime
        point = self.env["gps.tracking.point"].search(
            [("device_id", "=", self.id), ("timestamp", "<=", target_datetime)],
            order="timestamp desc",
            limit=1,
        )

        if not point:
            return False

        # Get fuel data from point
        fuel_percentage = point.fuel_level
        fuel_deciliters = point.fuel_level_l  # This field is in deciliters

        # Convert based on configuration
        percentage = self.config_id.get_fuel_level_percentage(
            fuel_percentage=fuel_percentage,
            fuel_deciliters=fuel_deciliters,
            vehicle=self.vehicle_id,
        )
        liters = self.config_id.get_fuel_level_liters(
            fuel_percentage=fuel_percentage,
            fuel_deciliters=fuel_deciliters,
            vehicle=self.vehicle_id,
        )

        if percentage is False and liters is False:
            return False

        return {
            "percentage": percentage,
            "liters": liters,
            "raw_percentage": fuel_percentage,
            "raw_deciliters": fuel_deciliters,
        }
