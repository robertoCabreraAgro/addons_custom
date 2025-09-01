import logging

from datetime import datetime, timezone
from functools import wraps
from typing import Dict, Any, Optional, Tuple

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


def log_webhook_activity(func):
    """Decorator to log webhook activity and performance"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = datetime.now()
        remote_addr = request.httprequest.remote_addr

        try:
            result = func(*args, **kwargs)
            duration = (datetime.now() - start_time).total_seconds()
            _logger.info(
                "GPS webhook processed successfully from %s in %.3fs",
                remote_addr,
                duration,
            )
            return result
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            _logger.error(
                "GPS webhook failed from %s after %.3fs: %s",
                remote_addr,
                duration,
                str(e),
                exc_info=True,
            )
            raise

    return wrapper


class GPSWebhook(http.Controller):
    """
    Controller for handling GPS tracking webhooks

    This controller receives GPS tracking data from IoT devices,
    validates the data, and stores it in the database.
    """

    # Response codes
    RESPONSE_SUCCESS = b"\x01"
    RESPONSE_FAILURE = b"\x00"

    # Field mapping from GPS data to model fields
    FIELD_MAPPING = {
        "alt": "altitude",
        "ang": "angle",
        "evt": "event_type",
        "latlng": "latitude_longitude",
        "pr": "priority",
        "sat": "satellites",
        "sp": "speed",
        "ts": "timestamp",
        "11": "iccid1",
        "14": "imei",
        "16": "total_odometer",
        "21": "gsm_signal",
        "66": "external_voltage",
        "67": "battery_voltage",
        "68": "battery_current",
        "69": "gnss_status",
        "81": "wheel_speed",
        "84": "fuel_level_l",
        "85": "engine_speed_rpm",
        "87": "odometer",
        "89": "fuel_level",
        "102": "engine_total_hours",
        "103": "engine_total_hours_counted",
        "107": "fuel_consumed_counted",
        "115": "engine_temperature",
        "123": "control_state_flags",
        "175": "auto_geofence",
        "181": "gnss_pdop",
        "182": "gnss_hdop",
        "200": "sleep_mode",
        "239": "ignition",
        "240": "movement",
        "241": "active_gsm_operator",
        "653": "parking_brake_state",
        "662": "central_lock",
        "953": "isf_check_engine_indicator",
    }

    # Special field handlers
    SPECIAL_FIELDS = {"latitude_longitude", "timestamp", "odometer"}

    # Validation constraints
    MIN_TIMESTAMP = 946684800000  # Jan 1, 2000 in milliseconds
    MAX_TIMESTAMP = 2147483647000  # Jan 19, 2038 in milliseconds
    MIN_LATITUDE = -90.0
    MAX_LATITUDE = 90.0
    MIN_LONGITUDE = -180.0
    MAX_LONGITUDE = 180.0

    # ==================== Validation Methods ====================

    def _validate_timestamp(self, timestamp: int) -> bool:
        """Validate timestamp is within reasonable bounds"""
        return (
            isinstance(timestamp, (int, float))
            and self.MIN_TIMESTAMP <= timestamp <= self.MAX_TIMESTAMP
        )

    def _validate_coordinates(self, lat: float, lng: float) -> bool:
        """Validate GPS coordinates are within valid ranges"""
        try:
            lat_float = float(lat)
            lng_float = float(lng)
            return (
                self.MIN_LATITUDE <= lat_float <= self.MAX_LATITUDE
                and self.MIN_LONGITUDE <= lng_float <= self.MAX_LONGITUDE
            )
        except (ValueError, TypeError):
            return False

    # ==================== Data Processing Methods ====================

    def _parse_coordinates(
        self, latlng_str: str
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Parse latitude and longitude from comma-separated string

        Args:
            latlng_str: Comma-separated latitude,longitude string

        Returns:
            Tuple of (latitude, longitude) or (None, None) if invalid
        """
        try:
            if not latlng_str or "," not in latlng_str:
                _logger.warning("Invalid coordinate format: %s", latlng_str)
                return None, None

            lat_str, lng_str = latlng_str.split(",", 1)
            lat = float(lat_str.strip())
            lng = float(lng_str.strip())

            if not self._validate_coordinates(lat, lng):
                _logger.warning("Coordinates out of range: lat=%s, lng=%s", lat, lng)
                return None, None

            return lat, lng
        except (ValueError, AttributeError) as e:
            _logger.warning("Failed to parse coordinates '%s': %s", latlng_str, e)
            return None, None

    def _process_timestamp(self, timestamp_ms: int) -> Optional[datetime]:
        """
        Convert millisecond timestamp to datetime

        Args:
            timestamp_ms: Timestamp in milliseconds

        Returns:
            Datetime object or None if invalid
        """
        try:
            if not self._validate_timestamp(timestamp_ms):
                _logger.warning("Invalid timestamp: %s", timestamp_ms)
                return None

            # Convert from milliseconds to seconds and create datetime
            return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).replace(
                tzinfo=None
            )
        except (ValueError, OSError, TypeError) as e:
            _logger.warning("Failed to process timestamp %s: %s", timestamp_ms, e)
            return None

    def _process_odometer(self, value: float) -> Optional[float]:
        """
        Process odometer value (convert from meters to kilometers)

        Args:
            value: Odometer value in meters

        Returns:
            Odometer value in kilometers or None if invalid
        """
        try:
            odometer_value = float(value) / 1000.0
            if odometer_value < 0:
                _logger.warning("Negative odometer value: %s", odometer_value)
                return None
            return odometer_value
        except (ValueError, TypeError) as e:
            _logger.warning("Failed to process odometer %s: %s", value, e)
            return None

    # ==================== Request Processing Methods ====================

    def _extract_payload(self, json_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract payload from JSON data structure

        Args:
            json_data: Raw JSON data from request

        Returns:
            Extracted payload or None if extraction fails
        """
        try:
            if not json_data:
                _logger.debug("Empty JSON data received")
                return None

            # Navigate through the expected structure
            state = json_data.get("state", {})
            if not isinstance(state, dict):
                _logger.warning("Invalid 'state' structure in payload")
                return None

            reported = state.get("reported", {})
            if not isinstance(reported, dict):
                _logger.warning("Invalid 'reported' structure in payload")
                return None

            return reported

        except Exception as e:
            _logger.error("Failed to extract payload: %s", e, exc_info=True)
            return None

    def _process_field_value(
        self, vals: Dict[str, Any], field_name: str, value: Any
    ) -> None:
        """
        Process individual field value based on field type

        Args:
            field_name: Model field name
            value: Raw value from GPS data
            vals: Dictionary to store processed values
        """
        try:
            if field_name == "latitude_longitude":
                lat, lng = self._parse_coordinates(value)
                if lat is not None and lng is not None:
                    vals["latitude"] = lat
                    vals["longitude"] = lng

            elif field_name == "timestamp":
                processed_ts = self._process_timestamp(value)
                if processed_ts:
                    vals[field_name] = processed_ts

            elif field_name == "odometer":
                processed_odo = self._process_odometer(value)
                if processed_odo is not None:
                    vals[field_name] = processed_odo

            else:
                # Store value directly for other fields
                vals[field_name] = value

        except Exception as e:
            _logger.warning(
                "Failed to process field '%s' with value '%s': %s", field_name, value, e
            )

    def _prepare_tracking_point_vals(
        self, payload: Dict[str, Any], device_id: int
    ) -> Dict[str, Any]:
        """
        Prepare values for creating tracking point record

        Args:
            payload: GPS data payload
            device_id: ID of the GPS device

        Returns:
            Dictionary of field values for tracking point
        """
        vals = {"device_id": device_id}

        # Get available fields from the model
        tracking_point_model = request.env["gps.tracking.point"].sudo()
        available_fields = set(tracking_point_model._fields.keys())

        # Process each mapped field
        for gps_field, model_field in self.FIELD_MAPPING.items():
            if gps_field not in payload:
                continue

            if model_field not in available_fields:
                continue

            value = payload[gps_field]
            if value is not None:
                self._process_field_value(vals, model_field, value)

        return vals

    # ==================== Database Operations ====================

    def _find_device(self, imei: str) -> Optional[Any]:
        """
        Find GPS tracking device by IMEI

        Args:
            imei: Device IMEI number

        Returns:
            Device record or None if not found
        """
        device = (
            request.env["gps.tracking.device"]
            .sudo()
            .search([("imei", "=", str(imei))], limit=1)
        )

        if not device:
            _logger.warning("Device not found for IMEI: %s", imei)

        return device

    def _create_tracking_point(self, vals: Dict[str, Any]) -> Optional[Any]:
        """
        Create new GPS tracking point record

        Args:
            vals: Field values for the new record

        Returns:
            Created record or None if creation fails
        """
        tracking_point = request.env["gps.tracking.point"].sudo()
        new_point = tracking_point.create(vals)
        return new_point


    def _update_device_last_point(self, device: Any, point_id: int) -> bool:
        """
        Update device's last tracking point reference

        Args:
            device: Device record
            point_id: ID of the new tracking point

        Returns:
            True if update successful, False otherwise
        """
        device.sudo().write({"last_point_id": point_id})
        return True

    # ==================== Main Webhook Endpoint ====================

    @http.route(
        "/gps/webhook",
        type="jsonrpc",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
    )
    @log_webhook_activity
    def gps_webhook(self, **kwargs) -> bytes:
        """
        Main webhook endpoint for GPS tracking data

        Receives GPS data from IoT devices, validates it,
        and stores tracking points in the database.

        Flow:
        1. Extract and validate JSON payload
        2. Find device by IMEI
        3. Process and validate GPS data fields
        4. Create tracking point record
        5. Update device's last known position

        Returns:
            Success (0x01) or failure (0x00) response byte
        """
        try:
            # Extract JSON data from request
            json_data = request.get_json_data()
            if not json_data:
                return self.RESPONSE_FAILURE

            # Extract payload from JSON structure
            payload = self._extract_payload(json_data)
            if not payload:
                return self.RESPONSE_FAILURE

            # Get device IMEI
            imei = payload.get("14")
            if not imei:
                return self.RESPONSE_FAILURE

            # Find device by IMEI
            device = self._find_device(imei)
            if not device:
                return self.RESPONSE_FAILURE

            # Prepare tracking point values
            vals = self._prepare_tracking_point_vals(payload, device.id)

            # Create tracking point
            new_point = self._create_tracking_point(vals)
            if not new_point:
                return self.RESPONSE_FAILURE

            # Update device's last point
            self._update_device_last_point(device, new_point.id)

            return self.RESPONSE_SUCCESS

        except Exception as e:
            _logger.error("Unexpected error in GPS webhook: %s", e, exc_info=True)
            return self.RESPONSE_FAILURE
