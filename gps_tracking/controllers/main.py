import logging
from datetime import datetime, timezone

from odoo import http
from odoo.http import request

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
        "11": "iccid1",
        "16": "total_odometer",
        "21": "gsm_signal",
        "66": "external_voltage",
        "67": "battery_voltage",
        "68": "battery_current",
        "69": "gnss_status",
        "84": "fuel_level_l",
        "102": "engine_total_hours",
        "107": "fuel_consumed_counted",
        "123": "control_state_flags",
        "175": "auto_geofence",
        "181": "gnss_pdop",
        "182": "gnss_hdop",
        "200": "sleep_mode",
        "241": "active_gsm_operator",
        "pr": "priority",
        "evt": "event_type",
        "sat": "satellites",
    }

    @http.route(
        "/gps/webhook",
        type="jsonrpc",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
    )
    def gps_webhook(self, **kwargs):
        gps_tracking_point = request.env["gps.tracking.point"].sudo()
        _logger.debug(
            "Iniciando procesamiento del webhook GPS."
        )  # TODO: cambiar a debug luego de estabilizacion
        try:
            json_data = request.get_json_data() or {}
            _logger.debug(
                f"Payload recibido: {json_data}"
            )  # TODO: cambiar a debug luego de estabilizacion

            payload = json_data["state"]["reported"]
        except Exception as e:
            _logger.error(f"Error al procesar el JSON del payload: {e}")
            return b"\x00"

        try:
            if isinstance(payload, dict):
                imei = payload.get("14")
                if not imei:
                    _logger.warning("El payload no contiene el campo '14' (IMEI).")
                    return b"\x00"

                _logger.debug(f"Buscando dispositivo con IMEI: {imei}")
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

                _logger.debug(f"Dispositivo encontrado: {device.id} (IMEI: {imei})")
                vals = {"device_id": device.id}
                tracking_point_fields = gps_tracking_point._fields
                for gps_field, model_field in self.field_mapping.items():
                    if gps_field in payload:
                        value = payload[gps_field]
                        if model_field == "latitude_longitude":  # exceptional case
                            lat, lng = value.split(",")
                            vals["latitude"] = float(lat)
                            vals["longitude"] = float(lng)
                            continue
                        if model_field not in tracking_point_fields:
                            continue
                        if model_field == "timestamp":
                            try:
                                vals[model_field] = datetime.fromtimestamp(
                                    value / 1000, tz=timezone.utc
                                ).replace(tzinfo=None)
                            except Exception as e:
                                _logger.error(
                                    f"Error converting timestamp: {value} - {e}"
                                )
                                continue
                        elif model_field == "odometer":
                            vals[model_field] = value / 1000
                        else:
                            vals[model_field] = value

                _logger.debug(
                    f"Creando nuevo punto de seguimiento GPS: {vals}"
                )  # TODO: cambiar a debug luego de estabilizacion
                new_point = gps_tracking_point.create(vals)
                _logger.debug(
                    f"Punto de seguimiento creado exitosamente: ID {new_point.id}"
                )  # TODO: cambiar a debug luego de estabilizacion

                device.sudo().write({"last_point_id": new_point.id})
                _logger.debug(
                    f"Dispositivo actualizado con el último punto: ID {new_point.id}"
                )  # TODO: cambiar a debug luego de estabilizacion

                return b"\x01"

            else:
                _logger.warning("El payload no es un diccionario válido.")
                return b"\x00"

        except Exception as e:
            _logger.error(f"Error inesperado al procesar el payload: {e}")
            return b"\x00"
