import logging

import requests
from pyproj import Transformer

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class GpsTrackingPoint(models.Model):
    _name = "gps.tracking.point"
    _description = "GPS Tracking Point"
    _order = "timestamp desc"

    device_id = fields.Many2one(
        comodel_name="gps.tracking.device",
        string="Device",
        required=True,
        ondelete="cascade",
    )
    vehicle_id = fields.Many2one(
        comodel_name="fleet.vehicle",
        string="Vehícle",
        related="device_id.vehicle_id",
        store=True,
        readonly=True,
    )
    driver_name = fields.Char(
        string="Driver",
        compute="_compute_driver_name",
        store=True,
    )
    timestamp = fields.Datetime(string="Timestamp", required=True)
    priority = fields.Integer(string="Priority")
    altitude = fields.Float(string="Altitude")
    angle = fields.Float(string="Angle")
    satellites = fields.Integer(string="Satellites")
    speed = fields.Float(string="Speed")
    event_id = fields.Integer(string="Event ID")
    latitude = fields.Float(string="Latitude", digits=(16, 7))
    longitude = fields.Float(string="Longitude", digits=(16, 7))
    the_point = fields.GeoPoint(
        string="Position",
        srid=3857,
        compute="_compute_the_point",
        store=True,
    )
    address = fields.Char(string="Address", compute="_compute_address", store=True)
    ignition = fields.Integer(string="Ignition")
    movement = fields.Integer(string="Movement")
    gsm_signal = fields.Integer(string="GSM Signal")
    sleep_mode = fields.Integer(string="Sleep Mode")
    gnss_status = fields.Integer(string="GNSS Status")
    gnss_pdop = fields.Float(string="GNSS PDOP", digits=(16, 2))
    gnss_hdop = fields.Float(string="GNSS HDOP", digits=(16, 2))
    external_voltage = fields.Float(string="External Voltage", digits=(16, 3))
    battery_voltage = fields.Float(string="Battery Voltage", digits=(16, 3))
    battery_current = fields.Float(string="Battery Current", digits=(16, 3))
    active_gsm_operator = fields.Integer(string="Active GSM Operator")
    odometer = fields.Integer(string="Odometer")
    fuel_level = fields.Integer(string="Fuel Level")
    wheel_speed = fields.Float(string="Wheel Speed")
    engine_speed_rpm = fields.Integer(string="Engine Speed (RPM)")
    engine_total_hours_counted = fields.Float(
        string="Engine Total Hours Counted", digits=(16, 2)
    )
    engine_temperature = fields.Float(string="Engine Temperature", digits=(16, 2))
    parking_brake_state = fields.Integer(string="Parking Brake State")
    central_lock = fields.Integer(string="Central Lock")
    isf_check_engine_indicator = fields.Integer(string="ISF Check Engine Indicator")
    iccid1 = fields.Char(string="ICCID1")
    total_odometer = fields.Integer(string="Total Odometer")
    fuel_level_l = fields.Float(string="Fuel Level (L)", digits=(16, 2))
    engine_total_hours = fields.Float(string="Engine Total Hours", digits=(16, 2))
    fuel_consumed_counted = fields.Float(string="Fuel Consumed Counted", digits=(16, 2))
    control_state_flags = fields.Char(
        string="Control State Flags",
        help="This is an hexadecimal flag to check vehicle state",
    )
    auto_geofence = fields.Integer(string="Auto Geofence")
    event_type = fields.Char(string="Event Type")

    @api.depends("device_id")
    def _compute_driver_name(self):
        for point in self:
            point.driver_name = point.device_id.driver_name

    @api.depends("latitude", "longitude")
    def _compute_the_point(self):
        transformer = Transformer.from_crs(4326, 3857, always_xy=True)
        for point in self:
            if point.latitude and point.longitude and not point.the_point:
                _logger.info(
                    f"Transformando latitud {point.latitude} y longitud {point.longitude} de SRID 4326 a SRID 3857."
                )
                x, y = transformer.transform(point.longitude, point.latitude)
                point.the_point = f"POINT({x} {y})"
            elif point.the_point:
                _logger.info(f"Punto ya calculado: {point.the_point}")

    def _compute_address(self):
        #     api_key = ''  #Sustituye por tu clave de API
        for point in self:
            point.address = ""

    #         _logger.info(f"Ejecutando _compute_address para ID {point.id} con latitude={point.latitude}, longitude={point.longitude}")
    #         if point.latitude and point.longitude:
    #             url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={point.latitude},{point.longitude}&key={api_key}"
    #             try:
    #                 response = requests.get(url)
    #                 if response.status_code == 200:
    #                     data = response.json()
    #                     if data['results']:
    #                         point.address = data['results'][0]['formatted_address']
    #                         _logger.info(f"Dipointción obtenida para ID {point.id}: {point.address}")
    #                     else:
    #                         point.address = "Address not found"
    #                         _logger.warning(f"Sin resultados para las coordenadas ID {point.id}: {url}")
    #                 else:
    #                     _logger.error(f"Error al consultar la API de Google Maps para ID {point.id}: {response.status_code}")
    #                     point.address = "Error fetching address"
    #             except Exception as e:
    #                 _logger.exception(f"Excepción al consultar la API de Google Maps para ID {point.id}: {e}")
    #                 point.address = "Error fetching address"
    #         else:
    #             point.address = "Coordinates not set"
    #             _logger.warning(f"Coordenadas no establecidas para ID {point.id}")
