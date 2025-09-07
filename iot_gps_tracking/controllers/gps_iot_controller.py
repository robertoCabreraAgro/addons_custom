import logging

from odoo import http, _
from odoo.exceptions import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class GPSIoTController(http.Controller):
    """Controller to bridge GPS webhooks with IoT infrastructure"""

    @http.route(
        "/gps/iot/webhook", type="json", auth="public", methods=["POST"], csrf=False
    )
    def gps_iot_webhook(self, **kwargs):
        """
        Bridge endpoint to receive GPS data and route through IoT infrastructure.
        This maintains compatibility with existing GPS webhook integrations while
        leveraging the IoT framework for device management and real-time updates.

        Expected data format:
        {
            'imei': 'device_imei',
            'data': {
                'latitude': float,
                'longitude': float,
                'timestamp': datetime,
                'speed': float,
                'altitude': float,
                'satellites': int,
                ...
            }
        }
        """
        try:
            # Extract GPS data
            data = request.jsonrequest
            imei = data.get("imei") or kwargs.get("imei")
            gps_data = data.get("data", {})

            # Merge kwargs into gps_data for flexibility
            for key in [
                "latitude",
                "longitude",
                "timestamp",
                "speed",
                "altitude",
                "satellites",
            ]:
                if key in kwargs and key not in gps_data:
                    gps_data[key] = kwargs[key]

            if not imei:
                return {"status": "error", "message": "IMEI is required"}

            # Find or create IoT device
            iot_device = (
                request.env["iot.device"]
                .sudo()
                .search(
                    [("gps_imei", "=", imei), ("type", "=", "gps_tracker")], limit=1
                )
            )

            if not iot_device:
                # Auto-register new GPS device
                _logger.info(f"Auto-registering new GPS device with IMEI: {imei}")
                iot_device = self._register_gps_device(imei, gps_data)

            # Process GPS data through IoT channel
            if iot_device.iot_id:
                # Send through WebSocket for real-time processing
                request.env["iot.channel"].sudo().send_message(
                    {
                        "iot_identifiers": [iot_device.iot_id.identifier],
                        "device_identifiers": [iot_device.identifier],
                        "action": "process_gps_data",
                        "gps_data": gps_data,
                    },
                    "iot_action",
                )

            # Store tracking point in database
            tracking_point = iot_device.process_gps_position(gps_data)

            _logger.debug(
                f"GPS data processed for device {imei}: "
                f"lat={gps_data.get('latitude')}, lon={gps_data.get('longitude')}"
            )

            return {
                "status": "success",
                "device_id": iot_device.id,
                "tracking_point_id": tracking_point.id if tracking_point else None,
                "message": "GPS data received and processed",
            }

        except Exception as e:
            _logger.error(f"GPS IoT webhook error: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    @http.route(
        "/gps/iot/status/<string:imei>", type="json", auth="public", methods=["GET"]
    )
    def gps_device_status(self, imei, **kwargs):
        """
        Get status of a GPS device

        :param imei: Device IMEI
        :return: Device status information
        """
        try:
            # Find IoT device
            iot_device = (
                request.env["iot.device"]
                .sudo()
                .search(
                    [("gps_imei", "=", imei), ("type", "=", "gps_tracker")], limit=1
                )
            )

            if not iot_device:
                return {"status": "error", "message": "Device not found"}

            return {
                "status": "success",
                "device": {
                    "id": iot_device.id,
                    "name": iot_device.name,
                    "imei": iot_device.gps_imei,
                    "connected": iot_device.connected_status == "connected",
                    "tracking_enabled": iot_device.gps_tracking_enabled,
                    "last_update": (
                        iot_device.gps_last_update.isoformat()
                        if iot_device.gps_last_update
                        else None
                    ),
                    "last_position": (
                        {
                            "latitude": iot_device.gps_last_latitude,
                            "longitude": iot_device.gps_last_longitude,
                            "speed": iot_device.gps_last_speed,
                            "altitude": iot_device.gps_last_altitude,
                        }
                        if iot_device.gps_last_latitude
                        else None
                    ),
                    "battery_level": iot_device.gps_battery_level,
                    "ignition": iot_device.gps_ignition_state,
                    "movement": iot_device.gps_movement_state,
                },
            }

        except Exception as e:
            _logger.error(f"GPS status error: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    @http.route(
        "/gps/iot/command", type="json", auth="public", methods=["POST"], csrf=False
    )
    def gps_device_command(self, **kwargs):
        """
        Send command to GPS device

        Expected data:
        {
            'imei': 'device_imei',
            'command': 'start_tracking|stop_tracking|get_position',
            'params': {}
        }
        """
        try:
            data = request.jsonrequest
            imei = data.get("imei")
            command = data.get("command")
            params = data.get("params", {})

            if not imei or not command:
                return {"status": "error", "message": "IMEI and command are required"}

            # Find IoT device
            iot_device = (
                request.env["iot.device"]
                .sudo()
                .search(
                    [("gps_imei", "=", imei), ("type", "=", "gps_tracker")], limit=1
                )
            )

            if not iot_device:
                return {"status": "error", "message": "Device not found"}

            # Map commands to actions
            action_map = {
                "start_tracking": "start_tracking",
                "stop_tracking": "stop_tracking",
                "get_position": "get_position",
                "set_interval": "set_interval",
            }

            action = action_map.get(command)
            if not action:
                return {"status": "error", "message": f"Unknown command: {command}"}

            # Send command through IoT channel
            if iot_device.iot_id:
                request.env["iot.channel"].sudo().send_message(
                    {
                        "iot_identifiers": [iot_device.iot_id.identifier],
                        "device_identifiers": [iot_device.identifier],
                        "action": action,
                        **params,
                    },
                    "iot_action",
                )

            # Update device state if needed
            if command == "start_tracking":
                iot_device.gps_tracking_enabled = True
            elif command == "stop_tracking":
                iot_device.gps_tracking_enabled = False

            return {
                "status": "success",
                "message": f"Command {command} sent to device {imei}",
            }

        except Exception as e:
            _logger.error(f"GPS command error: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def _register_gps_device(self, imei, initial_data):
        """
        Auto-register a new GPS device as IoT device

        :param imei: Device IMEI
        :param initial_data: Initial GPS data
        :return: Created IoT device record
        """
        try:
            # Get or create virtual IoT box for GPS devices
            gps_box = request.env["iot.box"].sudo().get_or_create_gps_virtual_box()

            # Look for existing GPS configuration
            gps_config = request.env["iot.gps.config"].sudo().search([], limit=1)

            # Create IoT device
            iot_device = (
                request.env["iot.device"]
                .sudo()
                .create(
                    {
                        "name": f"GPS {imei}",
                        "identifier": f"gps_{imei}",
                        "type": "gps_tracker",
                        "iot_id": gps_box.id,
                        "connection": "network",
                        "gps_imei": imei,
                        "gps_config_id": gps_config.id if gps_config else False,
                        "connected_status": "connected",
                        "gps_tracking_enabled": True,
                    }
                )
            )

            # No legacy device linking since we're independent

            _logger.info(
                f"GPS device auto-registered: {iot_device.name} (ID: {iot_device.id})"
            )

            return iot_device

        except Exception as e:
            _logger.error(f"Failed to register GPS device {imei}: {e}", exc_info=True)
            raise ValidationError(_("Failed to register GPS device: %s") % str(e))

    @http.route(
        "/gps/iot/batch", type="json", auth="public", methods=["POST"], csrf=False
    )
    def gps_batch_update(self, **kwargs):
        """
        Process batch GPS updates for multiple devices

        Expected data:
        {
            'updates': [
                {
                    'imei': 'device_imei',
                    'data': {...}
                },
                ...
            ]
        }
        """
        try:
            data = request.jsonrequest
            updates = data.get("updates", [])

            results = []
            for update in updates:
                try:
                    result = self.gps_iot_webhook(
                        imei=update.get("imei"), data=update.get("data", {})
                    )
                    results.append(result)
                except Exception as e:
                    results.append(
                        {
                            "status": "error",
                            "imei": update.get("imei"),
                            "message": str(e),
                        }
                    )

            return {"status": "success", "processed": len(results), "results": results}

        except Exception as e:
            _logger.error(f"GPS batch update error: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}
