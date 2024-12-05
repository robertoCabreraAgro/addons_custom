from odoo import fields, models, api
from pyproj import Transformer
import logging

_logger = logging.getLogger(__name__)

class GpsTrackingDevice(models.Model):
    _name = 'gps.tracking.device'
    _description = 'GPS Tracking Device'
    
    imei = fields.Char(string='IMEI', required=True, unique=True)
    tracking_points = fields.One2many('gps.tracking.point', 'device_id', string='Tracking Points')
    last_point_id = fields.Many2one('gps.tracking.point', string='Last Tracking Point', compute='_compute_last_point', store=True)
    speed = fields.Float(string='Speed', related='last_point_id.speed', store=True)
    timestamp = fields.Datetime(string='Timestamp', related='last_point_id.timestamp', store=True)
    altitude = fields.Float(string='Altitude', related='last_point_id.altitude', store=True)
    the_point = fields.GeoPoint(string='Current Position', related='last_point_id.the_point', store=True)
    history_route = fields.GeoLine(string='History Route', compute='_compute_history_route', store=True, srid=3857,)

    @api.depends('tracking_points.timestamp')
    def _compute_last_point(self):
        for device in self:
            # Encuentra el último punto basándose en el timestamp
            last_point = device.tracking_points.sorted('timestamp', reverse=True)[:1]
            device.last_point_id = last_point.id if last_point else False


    @api.depends('tracking_points.latitude', 'tracking_points.longitude')
    def _compute_history_route(self):
        transformer = Transformer.from_crs(4326, 3857, always_xy=True)
        for device in self:
            points = device.tracking_points.sorted('timestamp')
            coords = []
            for point in points:
                if point.latitude and point.longitude:
                    x, y = transformer.transform(point.longitude, point.latitude)
                    coords.append(f"{x} {y}")
            if len(coords) > 1:
                device.history_route = f"LINESTRING({', '.join(coords)})"
            else:
                device.history_route = False


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

    the_point = fields.GeoPoint(string='Position', srid=3857, compute='_compute_the_point', store=True)

    @api.depends('latitude', 'longitude')
    def _compute_the_point(self):
        transformer = Transformer.from_crs(4326, 3857, always_xy=True)
        for rec in self:
            if rec.latitude and rec.longitude:
                _logger.info(f"Transformando latitud {rec.latitude} y longitud {rec.longitude} de SRID 4326 a SRID 3857.")
                x, y = transformer.transform(rec.longitude, rec.latitude)
                rec.the_point = f'POINT({x} {y})'
                _logger.info(f"Coordenadas transformadas: {x}, {y} (SRID 3857).")
            else:
                _logger.warning(f"Faltan latitud o longitud en el registro {rec.id}, no se puede convertir a SRID 3857.")
                rec.the_point = False