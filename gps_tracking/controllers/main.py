import logging

from odoo.http import request

from odoo import http

_logger = logging.getLogger(__name__)
LAST_IMEI_REQUEST = {}
import json

class GPSWebhook(http.Controller):

    @http.route(
        "/gps/webhook", type="http", auth="public", methods=["POST"], csrf=False
    )
    @http.route(
        "/gps/webhook", type="json", auth="public", methods=["POST"], csrf=False
    )
    def gps_webhook(self, **kwargs):
        _logger.info("Processing GPS webhook response")
        try:
            # Try to get the JSON payload from HTTP data
            response = request.httprequest
            byte_str = response.data
            payload = json.loads(byte_str.decode('utf-8'))
        except Exception as e:
            _logger.error(f"Error processing HTTP data: {e}")
            try:
                # If HTTP data fails, try to get the JSON payload directly
                payload = request.jsonrequest
            except Exception as e:
                _logger.warning(f"Error processing JSON data: {e}")
                return b'\x00'

        try:
            if isinstance(payload, dict):
                imei = payload.get("imei")
                data = payload.get("data")

                if imei:
                    imei_checker = request.env["gps.tracking.log"].sudo().imei_checker(hex_imei=imei)
                    if imei_checker:
                        imei = request.env["gps.tracking.log"].sudo().ascii_imei_converter(imei)
                    else:
                        return b'\x00'
                    device = request.env["gps.tracking.device"].sudo().search([("imei", "=", imei)], limit=1)
                    if not device:
                        device = request.env["gps.tracking.device"].sudo().create({"imei": imei})
                        _logger.info(f"Device created: {device}")
                    LAST_IMEI_REQUEST["imei"] = imei
                    return b'\x01'
                elif data:
                    if LAST_IMEI_REQUEST.get("imei"):
                        imei = LAST_IMEI_REQUEST.get("imei")
                        device = request.env["gps.tracking.device"].sudo().search([("imei", "=", imei)], limit=1)
                        if not device:
                            _logger.warning(f"Device not found: {imei}")
                            return b'\x00'
                        request.env["gps.tracking.log"].sudo().input_trigger(data, imei)
                    # request.env["gps.tracking.log"].sudo().input_trigger()
                        return b'\x01'
                    else:
                        _logger.warning("No IMEI found")
                        return b'\x00'

            elif payload:
                if LAST_IMEI_REQUEST.get("imei"):
                    imei = LAST_IMEI_REQUEST.get("imei")
                    device = request.env["gps.tracking.device"].sudo().search([("imei", "=", imei)], limit=1)
                    if not device:
                        _logger.warning(f"Device not found: {imei}")
                        return b'\x00'
                    request.env["gps.tracking.log"].sudo().input_trigger(payload=payload, imei=imei)
                    return b'\x01'
                _logger.warning("No IMEI found")
                return b'\x00'
            else:
                _logger.info("Empty payload")
                return b'\x00'
        except Exception as e:
            _logger.error(f"Error processing payload: {e}")
            return b'\x00'