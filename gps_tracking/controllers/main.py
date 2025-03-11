import logging
from odoo import http
from odoo.http import request

from datetime import datetime


_logger = logging.getLogger(__name__)


class GPSWebhook(http.Controller):

    field_mapping = {
        "14": "imei",
        "81": "wheel_speed",
        "85": "engine_speed_rpm",
        "87": "odometer",
        "89": "fuel_level",
        "103": "engine_total_hours_counted",
        "115": "engine_temperature",
        "239": "ignition",
        "240": "movement",
        "653": "parking_brake_state",
        "662": "central_lock",
        "953": "isf_check_engine_indicator",
        "ts": "timestamp",
        "latlng": "latitude_longitude",
        "alt": "altitude",
        "ang": "angle",
        "sp": "speed",
    }

    @http.route(
        "/gps/webhook", type="jsonrpc", auth="public", methods=["POST"], csrf=False
    )
    def gps_webhook(self, **kwargs):
        _logger.info(
            "Iniciando procesamiento del webhook GPS."
        )  # TODO: cambiar a debug luego de estabilizacion
        try:
            json_data = request.jsonrequest or {}
            payload = json_data["state"]["reported"]
            _logger.info(
                f"Payload recibido: {json_data}"
            )  # TODO: cambiar a debug luego de estabilizacion
        except Exception as e:
            _logger.error(f"Error al procesar el JSON del payload: {e}")
            return b"\x00"

        try:
            if isinstance(payload, dict):
                imei = payload.get("14")
                if not imei:
                    _logger.warning("El payload no contiene el campo '14' (IMEI).")
                    return b"\x00"

                _logger.info(f"Buscando dispositivo con IMEI: {imei}")
                device = (
                    request.env["gps.tracking.device"]
                    .sudo()
                    .search([("imei", "=", imei)], limit=1)
                )
                if not device:
                    _logger.warning(
                        f"No se encontró ningún dispositivo con IMEI: {imei}"
                    )
                    return b"\x00"

                _logger.info(f"Dispositivo encontrado: {device.id} (IMEI: {imei})")
                vals = {"device_id": device.id}

                for gps_field, model_field in self.field_mapping.items():
                    if gps_field in payload:
                        value = payload[gps_field]
                        if model_field == "timestamp":
                            try:
                                vals[field] = datetime.utcfromtimestamp(value / 1000)
                            except Exception as e:
                                _logger.error(
                                    f"Error converting timestamp: {value} - {e}"
                                )
                                continue
                        elif model_field == "latitude_longitude":
                            lat, lng = value.split(",")
                            vals["latitude"] = float(lat)
                            vals["longitude"] = float(lng)
                        elif model_field == "odometer":
                            vals[field] = value / 1000
                        else:
                            vals[field] = value

                _logger.info(
                    "Creando nuevo punto de seguimiento GPS."
                )  # TODO: cambiar a debug luego de estabilizacion
                new_point = request.env["gps.tracking.point"].sudo().create(vals)
                _logger.info(
                    f"Punto de seguimiento creado exitosamente: ID {new_point.id}"
                )  # TODO: cambiar a debug luego de estabilizacion

                device.sudo().write({"last_point_id": new_point.id})
                _logger.info(
                    f"Dispositivo actualizado con el último punto: ID {new_point.id}"
                )  # TODO: cambiar a debug luego de estabilizacion

                return b"\x01"

            else:
                _logger.warning("El payload no es un diccionario válido.")
                return b"\x00"

        except Exception as e:
            _logger.error(f"Error inesperado al procesar el payload: {e}")
            return b"\x00"
