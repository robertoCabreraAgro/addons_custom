import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class GpsGeofence(models.Model):
    _name = "gps.geofence"
    _description = "Geofence"

    name = fields.Char(string="Geofence Name", required=True)
    geometry = fields.GeoPolygon(string="Geofence Area", required=True)
    color = fields.Char(
        string="Color", default="#FF0000"
    )  # Para diferenciar en el mapa
    active = fields.Boolean(string="Active", default=True)
