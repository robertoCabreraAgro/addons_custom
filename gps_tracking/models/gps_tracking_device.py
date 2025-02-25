from odoo import fields, models, api
from pyproj import Transformer
import logging
import requests

_logger = logging.getLogger(__name__)

class GpsTrackingDevice(models.Model):
    _name = 'gps.tracking.device'
    _description = 'GPS Tracking Device'
    
    imei = fields.Char(string='IMEI', required=True, unique=True)
    tracking_points = fields.One2many('gps.tracking.point', 'device_id', string='Tracking Points')
    last_point_id = fields.Many2one('gps.tracking.point', string='Last Tracking Point')
    speed = fields.Float(string='Speed', related='last_point_id.speed', store=True)
    satellite = fields.Integer(string='Satélites', related='last_point_id.satellites', store=True)
    timestamp = fields.Datetime(string='Timestamp', related='last_point_id.timestamp', store=True)
    altitude = fields.Float(string='Altitude', related='last_point_id.altitude', store=True)
    address = fields.Char(string='Altitude', related='last_point_id.address', store=True)
    #the_point = fields.GeoPoint(string='Current Position', related='last_point_id.the_point', store=True)
    #history_route = fields.GeoLine(string='History Route', compute='_compute_history_route', store=True, srid=3857,)
    gsm_signal = fields.Integer(string="Gsm Signal", related='last_point_id.gsm_signal', store=True)
    ignition = fields.Integer(string='Ignition (239)', related='last_point_id.ignition', store=True)
    movement = fields.Integer(string='Movement (240)', related='last_point_id.movement', store=True)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', help='Vehículo asociado al dispositivo GPS')
    color = fields.Selection(
        selection=[
            ('#FF0000', 'Rojo'),
            ('#0000FF', 'Azul'),
            ('#008000', 'Verde'),
            ('#FFA500', 'Naranja'),
            ('#800080', 'Morado'),
            ('#000000', 'Negro'),
        ],
        string="Color de Recorrido",
        default='#FF0000'
    )
    
    #@api.depends('tracking_points.timestamp')  # Usar el campo correcto
    #def _compute_last_point(self):
    #    for rec in self:
    #        # Obtener el último punto usando tracking_points
    #        last_point = rec.tracking_points.sorted(key=lambda p: p.timestamp, reverse=True)[:1]
    #        rec.last_point_id = last_point.id if last_point else False
    #        
    #        # Log para depurar el valor del último punto
    #        if last_point:
    #            _logger.info(f"Dispositivo {rec.id}: Último punto actualizado a {last_point.id} con timestamp {last_point.timestamp}")
    #        else:
    #            _logger.warning(f"Dispositivo {rec.id}: No se encontraron puntos para actualizar el último punto.")


    #@api.depends('tracking_points.latitude', 'tracking_points.longitude')
    #def _compute_history_route(self):
    #    transformer = Transformer.from_crs(4326, 3857, always_xy=True)
    #    for device in self:
    #        points = device.tracking_points.sorted('timestamp')
    #        coords = []
    #        for point in points:
    #            if point.latitude and point.longitude:
    #                x, y = transformer.transform(point.longitude, point.latitude)
    #                coords.append(f"{x} {y}")
    #        if len(coords) > 1:
    #            device.history_route = f"LINESTRING({', '.join(coords)})"
    #        else:
    #            device.history_route = False
