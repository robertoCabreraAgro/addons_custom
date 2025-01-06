import logging
from pyproj import Transformer

from odoo import fields, models, api

_logger = logging.getLogger(__name__)


class GpsTrackingDevice(models.Model):
    _name = 'gps.tracking.device'
    _description = 'GPS Tracking Device'


    imei = fields.Char(
        string='IMEI',
        required=True,
    )
    log_ids = fields.One2many(
        'gps.tracking.log',
        'device_id',
        string='Tracking Points'
    )
    last_log_id = fields.Many2one(
        comodel_name='gps.tracking.log',
        string='Last Tracking Point',
        compute='_compute_last_point',
    )
    speed = fields.Float(related='last_log_id.speed', string='Speed')
    satellite = fields.Integer(related='last_log_id.satellites', string='Satélites')
    timestamp = fields.Datetime(related='last_log_id.timestamp', string='Timestamp')
    altitude = fields.Float(related='last_log_id.altitude', string='Altitude')
    address = fields.Char(related='last_log_id.address', string='Altitude')
    the_point = fields.GeoPoint(related='last_log_id.the_point', string='Current Position')


     _sql_constraints = [
         ('unique_imei', 'UNIQUE(imei)', 'This IMEI already exists')
     ]


    @api.depends('log_ids.timestamp')
    def _compute_last_point(self):
        for device in self:
            last_point = device.log_ids.sorted('timestamp', reverse=True)[:1]
            device.last_log_id = last_point.id if last_point else False


    @api.depends('log_ids.latitude', 'log_ids.longitude')
    def _compute_history_route(self):
        transformer = Transformer.from_crs(4326, 3857, always_xy=True)
        for device in self:
            points = device.log_ids.sorted('timestamp')
            coords = []
            for point in points:
                if point.latitude and point.longitude:
                    x, y = transformer.transform(point.longitude, point.latitude)
                    coords.append(f"{x} {y}")
            if len(coords) > 1:
                device.history_route = f"LINESTRING({', '.join(coords)})"
            else:
                device.history_route = False

    def enriquecer(self, diccionario):
        imei = diccionario["imei"]
        imei_id = self.search([("imei", "=", imei)])
        diccionario.update({"device_id": imei_id.id})
        return diccionario

