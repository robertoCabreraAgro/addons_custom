from odoo import fields, models, api
from pyproj import Transformer
import logging
import requests

_logger = logging.getLogger(__name__)


class GpsTrackingPoint(models.Model):
    _name = 'gps.tracking.point'
    _description = 'GPS Tracking Point'

    device_id = fields.Many2one('gps.tracking.device', string='Device', required=True, ondelete='cascade')
    timestamp = fields.Datetime(string='Timestamp', required=True)
    priority = fields.Integer(string='Priority')
    altitude = fields.Float(string='Altitude')
    angle = fields.Float(string='Angle')
    satellites = fields.Integer(string='Satellites')
    speed = fields.Float(string='Speed')
    event_id = fields.Integer(string='Event ID')

    latitude = fields.Float(string='Latitude', digits=(16, 7))
    longitude = fields.Float(string='Longitude', digits=(16, 7))
    #the_point = fields.GeoPoint(string='Position', srid=3857, compute='_compute_the_point', store=True)
    address = fields.Char(string='Address', compute='_compute_address', store=True)
    
    # Nuevos campos para los IO adicionales
    ignition = fields.Integer(string='Ignition')
    movement = fields.Integer(string='Movement')
    gsm_signal = fields.Integer(string='GSM Signal')
    sleep_mode = fields.Integer(string='Sleep Mode')
    gnss_status = fields.Integer(string='GNSS Status')
    gnss_pdop = fields.Float(string='GNSS PDOP', digits=(16, 2))
    gnss_hdop = fields.Float(string='GNSS HDOP', digits=(16, 2))
    external_voltage = fields.Float(string='External Voltage', digits=(16, 3))
    battery_voltage = fields.Float(string='Battery Voltage', digits=(16, 3))
    battery_current = fields.Float(string='Battery Current', digits=(16, 3))
    active_gsm_operator = fields.Integer(string='Active GSM Operator')
    odometer = fields.Integer(string='Total Odometer')
    fuel_level = fields.Integer(string="Fuel Level")
    
    #@api.depends('latitude', 'longitude')
    #def _compute_the_point(self):
    #    transformer = Transformer.from_crs(4326, 3857, always_xy=True)
    #    for rec in self:
    #        if rec.latitude and rec.longitude and not rec.the_point:
    #            _logger.info(f"Transformando latitud {rec.latitude} y longitud {rec.longitude} de SRID 4326 a SRID 3857.")
    #            x, y = transformer.transform(rec.longitude, rec.latitude)
    #            rec.the_point = f'POINT({x} {y})'
    #        elif rec.the_point:
    #            _logger.info(f"Punto ya calculado: {rec.the_point}")
                    

    # def _compute_address(self):
    #     api_key = ''  #Sustituye por tu clave de API
    #     for rec in self:
    #         _logger.info(f"Ejecutando _compute_address para ID {rec.id} con latitude={rec.latitude}, longitude={rec.longitude}")
    #         if rec.latitude and rec.longitude:
    #             url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={rec.latitude},{rec.longitude}&key={api_key}"
    #             try:
    #                 response = requests.get(url)
    #                 if response.status_code == 200:
    #                     data = response.json()
    #                     if data['results']:
    #                         rec.address = data['results'][0]['formatted_address']
    #                         _logger.info(f"Dirección obtenida para ID {rec.id}: {rec.address}")
    #                     else:
    #                         rec.address = "Address not found"
    #                         _logger.warning(f"Sin resultados para las coordenadas ID {rec.id}: {url}")
    #                 else:
    #                     _logger.error(f"Error al consultar la API de Google Maps para ID {rec.id}: {response.status_code}")
    #                     rec.address = "Error fetching address"
    #             except Exception as e:
    #                 _logger.exception(f"Excepción al consultar la API de Google Maps para ID {rec.id}: {e}")
    #                 rec.address = "Error fetching address"
    #         else:
    #             rec.address = "Coordinates not set"
    #             _logger.warning(f"Coordenadas no establecidas para ID {rec.id}")
