import logging

from pyproj import Transformer

from odoo import api, fields, models

# Inicializamos el logger
_logger = logging.getLogger(__name__)


class GpsTrackingDataHistory(models.Model):
    _name = "gps.tracking.data.history"
    _description = "GPS Tracking Data History"

    imei = fields.Char(string="IMEI", required=True)
    timestamp = fields.Datetime(string="Timestamp", required=True)
    priority = fields.Integer(string="Priority")
    altitude = fields.Float(string="Altitude")
    angle = fields.Float(string="Angle")
    satellites = fields.Integer(string="Satellites")
    speed = fields.Float(string="Speed")
    event_id = fields.Integer(string="Event ID")

    # Campos de latitud y longitud con mayor precisión (hasta 7 decimales)
    latitude = fields.Float(string="Latitude", digits=(16, 7))
    longitude = fields.Float(string="Longitude", digits=(16, 7))

    # Campo calculado que guarda las coordenadas en SRID 3857 (Web Mercator)
    the_point = fields.GeoPoint(
        string="Position", srid=3857, compute="_compute_the_point", store=True
    )
    # Nuevo campo para almacenar el recorrido histórico como una línea
    history_route = fields.GeoLine(
        string="History Route", compute="_compute_history_route", store=True
    )

    @api.depends("latitude", "longitude")
    def _compute_the_point(self):
        """Convierte lat/lng (SRID 4326) a SRID 3857 y guarda el resultado en the_point"""
        transformer = Transformer.from_crs(
            4326, 3857
        )  # Conversión de SRID 4326 a SRID 3857
        for rec in self:
            if rec.latitude and rec.longitude:
                # Log para saber qué coordenadas se están transformando
                _logger.info(
                    f"Transformando latitud {rec.latitude} y longitud {rec.longitude} de SRID 4326 a SRID 3857."
                )

                # Convertir las coordenadas
                x, y = transformer.transform(rec.latitude, rec.longitude)

                # Asignar el punto convertido en formato WKT
                rec.the_point = f"POINT({x} {y})"

                # Log del resultado de la transformación
                _logger.info(f"Coordenadas transformadas: {x}, {y} (SRID 3857).")
            else:
                _logger.warning(
                    f"Faltan latitud o longitud en el registro {rec.id}, no se puede convertir a SRID 3857."
                )
                rec.the_point = False

    @api.depends("latitude", "longitude", "imei", "timestamp")
    def _compute_history_route(self):
        transformer = Transformer.from_crs(4326, 3857)
        for rec in self:
            # Obtener todos los puntos históricos del mismo IMEI hasta el timestamp actual
            history_points = self.env["gps.tracking.data.history"].search(
                [("imei", "=", rec.imei), ("timestamp", "<=", rec.timestamp)],
                order="timestamp asc",
            )
            if history_points:
                points = []
                for point in history_points:
                    if point.latitude and point.longitude:
                        x, y = transformer.transform(point.latitude, point.longitude)
                        points.append(f"{x} {y}")
                if len(points) > 1:
                    line_wkt = f"LINESTRING({', '.join(points)})"
                    rec.history_route = line_wkt
                else:
                    rec.history_route = False
            else:
                rec.history_route = False

    def test_spatial_query(self):
        """Ejemplo de consulta espacial"""
        self.ensure_one()

        # Obtener máquinas que intersectan con la geometría actual
        matching_records = self.env["gps.tracking.data.history"].search(
            [("the_point", "geo_intersect", self.the_point)]
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Spatial Query",
                "message": f"Found {len(matching_records)} records intersecting with current point.",
                "sticky": False,
            },
        }
