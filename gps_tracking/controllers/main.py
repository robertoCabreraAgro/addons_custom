import logging

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


# Removed log_webhook_activity decorator - logging is now handled directly in webhook method


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

    # Data quality constraints for Teltonika devices
    MIN_SATELLITES_FOR_ACCURACY = 4  # Minimum satellites for good GPS accuracy
    MAX_REASONABLE_SPEED = 300  # Maximum reasonable speed in km/h for ground vehicles
    MIN_COORDINATE_PRECISION = 5  # Minimum decimal places for coordinates
    MAX_DUPLICATE_TIME_WINDOW = 30  # Seconds to check for duplicate points
    MAX_SPEED_CHANGE_PER_MINUTE = 100  # km/h - detect unrealistic speed changes
    MIN_ENGINE_TEMP = -40  # °C
    MAX_ENGINE_TEMP = 150  # °C

    # ------------------------------------------------------------
    # MAIN WEBHOOK ENDPOINT
    # ------------------------------------------------------------

    @http.route(
        "/gps/webhook",
        type="jsonrpc",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
    )
    def gps_webhook(self, **kwargs) -> bytes:
        """
        Webhook endpoint with comprehensive data quality validation and integrated logging.

        Receives GPS data from IoT devices, validates data quality,
        and stores tracking points in the database.

        Flow:
        1. Extract and validate JSON payload
        2. Find device by IMEI
        3. Process and validate GPS data fields
        4. Perform data quality validation
        5. Check for duplicates and temporal sequence
        6. Create tracking point record
        7. Update device's last known position

        Returns:
            Success (0x01) or failure (0x00) response byte
        """
        # Initialize performance tracking and logging
        start_time = datetime.now()
        remote_addr = (
            request.httprequest.remote_addr if request.httprequest else "unknown"
        )
        imei = "unknown"
        processing_stats = {
            "validation_start": datetime.now(),
            "validation_time": 0,
            "db_operation_time": 0,
            "quality_checks_passed": 0,
            "quality_checks_failed": 0,
        }

        try:
            # Extract JSON data from request
            json_data = request.get_json_data()
            if not json_data:
                _logger.warning("Empty JSON data received")
                return self.RESPONSE_FAILURE

            # Extract payload from JSON structure
            payload = self._extract_payload(json_data)
            if not payload:
                return self.RESPONSE_FAILURE

            # Get device IMEI
            # TODO - Support alternative identifiers if needed for example not Teltonika devices
            imei = payload.get("14")
            if not imei:
                _logger.warning("No IMEI found in payload from %s", remote_addr)
                return self.RESPONSE_FAILURE

            # Find device by IMEI
            device = self._get_device(imei)
            if not device:
                return self.RESPONSE_FAILURE

            # Prepare tracking point values
            vals = self._prepare_tracking_point_vals(device.id, payload)
            # TODO we need another mechanism to retur self.RESPONSE_FAILURE if no valid data
            if not vals.get("timestamp"):
                _logger.warning("No valid timestamp in GPS data for device %s", imei)
                return self.RESPONSE_FAILURE

            # === DATA QUALITY VALIDATION ===

            processing_stats["validation_start"] = datetime.now()

            # 1. Basic GPS quality validation (including speed validation)
            is_quality_valid, quality_error = self._validate_gps_quality(
                vals, device.id
            )
            if not is_quality_valid:
                processing_stats["quality_checks_failed"] += 1
                _logger.warning(
                    "GPS quality validation failed for device %s from %s: %s",
                    imei,
                    remote_addr,
                    quality_error,
                )
                # For non-critical quality issues, log but don't reject
                if (
                    "satellites" not in quality_error.lower()
                    and "precision" not in quality_error.lower()
                ):
                    self._log_webhook_failure(
                        start_time,
                        remote_addr,
                        imei,
                        f"Quality validation failed: {quality_error}",
                        processing_stats,
                    )
                    return self.RESPONSE_FAILURE
            else:
                processing_stats["quality_checks_passed"] += 1

            # 2. Check for duplicate points
            timestamp = vals.get("timestamp")
            latitude = vals.get("latitude")
            longitude = vals.get("longitude")

            if self._is_duplicate_point(device.id, timestamp, latitude, longitude):
                _logger.info(
                    "Duplicate GPS point ignored for device %s from %s",
                    imei,
                    remote_addr,
                )
                self._log_webhook_success(
                    start_time,
                    remote_addr,
                    imei,
                    "Duplicate point ignored",
                    processing_stats,
                    vals,
                )
                return self.RESPONSE_SUCCESS  # Return success to avoid device retries

            # 3. Validate temporal sequence
            is_sequence_valid, sequence_warning = self._validate_temporal_sequence(
                device.id, timestamp
            )

            if not is_sequence_valid:
                processing_stats["quality_checks_failed"] += 1
                _logger.warning(
                    "Temporal validation failed for device %s from %s: %s",
                    imei,
                    remote_addr,
                    sequence_warning,
                )
                # For temporal issues, we might want to be more lenient
                if "future" in sequence_warning.lower():
                    self._log_webhook_failure(
                        start_time,
                        remote_addr,
                        imei,
                        f"Temporal validation failed: {sequence_warning}",
                        processing_stats,
                    )
                    return self.RESPONSE_FAILURE  # Reject future timestamps
                # For speed change issues, log but accept (might be valid rapid acceleration/deceleration)
            else:
                processing_stats["quality_checks_passed"] += 1

            processing_stats["validation_time"] = (
                datetime.now() - processing_stats["validation_start"]
            ).total_seconds()

            # === CREATE TRACKING POINT ===

            db_start_time = datetime.now()
            new_point = self._create_tracking_point(vals)
            if not new_point:
                processing_stats["db_operation_time"] = (
                    datetime.now() - db_start_time
                ).total_seconds()
                self._log_webhook_failure(
                    start_time,
                    remote_addr,
                    imei,
                    "Failed to create tracking point",
                    processing_stats,
                )
                return self.RESPONSE_FAILURE

            # Update device's last point
            self._update_device_last_point(device, new_point.id)
            processing_stats["db_operation_time"] = (
                datetime.now() - db_start_time
            ).total_seconds()

            # Log successful processing with comprehensive metrics
            self._log_webhook_success(
                start_time,
                remote_addr,
                imei,
                "Point processed successfully",
                processing_stats,
                vals,
            )

            return self.RESPONSE_SUCCESS

        except Exception as e:
            self._log_webhook_failure(
                start_time,
                remote_addr,
                imei,
                f"Unexpected error: {str(e)}",
                processing_stats,
            )
            return self.RESPONSE_FAILURE

    # ------------------------------------------------------------
    # LOGGING HELPERS
    # ------------------------------------------------------------

    def _log_webhook_success(
        self,
        start_time: datetime,
        remote_addr: str,
        imei: str,
        message: str,
        processing_stats: dict,
        vals: dict = None,
    ):
        """
        Log successful webhook processing with comprehensive metrics.

        Args:
            start_time: Request start time
            remote_addr: Remote IP address
            imei: Device IMEI
            message: Success message
            processing_stats: Processing performance statistics
            vals: GPS values dictionary (optional)
        """
        total_duration = (datetime.now() - start_time).total_seconds()

        # Prepare quality metrics
        quality_metrics = {}
        if vals:
            quality_metrics = {
                "satellites": vals.get("satellites", "N/A"),
                "speed": vals.get("speed", "N/A"),
                "fuel_level": vals.get("fuel_level", "N/A"),
                "engine_temp": vals.get("engine_temperature", "N/A"),
                "coordinates": f"({vals.get('latitude', 'N/A')}, {vals.get('longitude', 'N/A')})",
            }

        # Log with structured format for monitoring systems
        _logger.info(
            "GPS_WEBHOOK_SUCCESS device=%s ip=%s duration=%.3fs validation=%.3fs db=%.3fs "
            "quality_passed=%d quality_failed=%d message='%s' metrics=%s",
            imei,
            remote_addr,
            total_duration,
            processing_stats.get("validation_time", 0),
            processing_stats.get("db_operation_time", 0),
            processing_stats.get("quality_checks_passed", 0),
            processing_stats.get("quality_checks_failed", 0),
            message,
            quality_metrics,
        )

    def _log_webhook_failure(
        self,
        start_time: datetime,
        remote_addr: str,
        imei: str,
        error_message: str,
        processing_stats: dict,
    ):
        """
        Log failed webhook processing with error details and performance metrics.

        Args:
            start_time: Request start time
            remote_addr: Remote IP address
            imei: Device IMEI
            error_message: Failure reason
            processing_stats: Processing performance statistics
        """
        total_duration = (datetime.now() - start_time).total_seconds()

        # Log with structured format for monitoring and alerting
        _logger.error(
            "GPS_WEBHOOK_FAILURE device=%s ip=%s duration=%.3fs validation=%.3fs db=%.3fs "
            "quality_passed=%d quality_failed=%d error='%s'",
            imei,
            remote_addr,
            total_duration,
            processing_stats.get("validation_time", 0),
            processing_stats.get("db_operation_time", 0),
            processing_stats.get("quality_checks_passed", 0),
            processing_stats.get("quality_checks_failed", 0),
            error_message,
        )

    # ------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------

    def _extract_payload(self, json_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract payload from JSON data structure

        Args:
            json_data: Raw JSON data from request

        Returns:
            Extracted payload or None if extraction fails
        """
        try:
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
                lat, lng = self._parse_latlong_coordinates(value)
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

            elif field_name == "engine_temperature":
                processed_odo = self._process_engine_temperature(value)
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
        self, device_id: int, payload: Dict[str, Any]
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

    # ------------------------------------------------------------
    # DATABASE OPERATIONS
    # ------------------------------------------------------------

    def _get_device(self, imei: str) -> Optional[Any]:
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

    # ------------------------------------------------------------
    # DATA PROCESING METHODS
    # ------------------------------------------------------------

    def _parse_latlong_coordinates(
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
                return None, None
            lat_str, lng_str = latlng_str.split(",", 1)
            lat = float(lat_str.strip())
            lng = float(lng_str.strip())
            if not self._validate_coordinates(lat, lng):
                return None, None
            return lat, lng
        except (ValueError, AttributeError) as e:
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
                return None
            # Convert from milliseconds to seconds and create datetime
            return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).replace(
                tzinfo=None
            )
        except (ValueError, OSError, TypeError) as e:
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
                return None
            return odometer_value
        except (ValueError, TypeError) as e:
            return None

    def _process_engine_temperature(self, value: float) -> Optional[float]:
        """
        Process odometer value (convert from meters to kilometers)

        Args:
            value: Odometer value in meters

        Returns:
            Odometer value in kilometers or None if invalid
        """
        try:
            temperature_value = float(value) / 10.0
            if temperature_value < 0:
                return None
            return temperature_value
        except (ValueError, TypeError) as e:
            return None

    # ------------------------------------------------------------
    # VALIDATIONS
    # ------------------------------------------------------------

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

    def _validate_gps_quality(
        self, vals: Dict[str, Any], device_id: int = None
    ) -> tuple[bool, str]:
        """
        Comprehensive GPS data quality validation.

        Args:
            vals: Dictionary of processed GPS values
            device_id: GPS device ID for advanced validations (optional)

        Returns:
            Tuple of (is_valid, error_message)
        """
        # 1. Validate coordinate quality
        is_valid, error = self._validate_coordinate_quality(vals)
        if not is_valid:
            return False, error

        # 2. Validate GPS accuracy
        is_valid, error = self._validate_gps_accuracy(vals)
        # if not is_valid:
        #     return False, error

        # 3. Validate speed parameters (includes speed change validation if device_id provided)
        is_valid, error = self._validate_speed_parameters(vals, device_id)
        # if not is_valid:
        #     return False, error

        # 4. Validate vehicle parameters
        is_valid, error = self._validate_vehicle_parameters(vals)
        # if not is_valid:
        #     return False, error

        # 5. Validate electrical systems
        is_valid, error = self._validate_electrical_parameters(vals)
        # if not is_valid:
        #     return False, error

        return True, "Valid"

    def _validate_gps_accuracy(self, vals: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate GPS signal accuracy based on satellite count.

        Args:
            vals: Dictionary of processed GPS values

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check GPS accuracy based on satellite count
        satellites = vals.get("satellites", 0)
        if satellites and satellites < self.MIN_SATELLITES_FOR_ACCURACY:
            return (
                False,
                f"Low GPS accuracy: only {satellites} satellites (minimum: {self.MIN_SATELLITES_FOR_ACCURACY})",
            )

        return True, "GPS accuracy valid"

    def _validate_coordinate_quality(self, vals: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate GPS coordinate quality and precision.

        Args:
            vals: Dictionary of processed GPS values

        Returns:
            Tuple of (is_valid, error_message)
        """
        lat = vals.get("latitude")
        lng = vals.get("longitude")

        if lat is None or lng is None:
            return True, "No coordinates to validate"

        # Check if coordinates have sufficient precision
        lat_precision = len(str(lat).split(".")[-1]) if "." in str(lat) else 0
        lng_precision = len(str(lng).split(".")[-1]) if "." in str(lng) else 0

        if (
            lat_precision < self.MIN_COORDINATE_PRECISION
            or lng_precision < self.MIN_COORDINATE_PRECISION
        ):
            return (
                False,
                f"Low coordinate precision: lat={lat_precision}, lng={lng_precision} decimals (minimum: {self.MIN_COORDINATE_PRECISION})",
            )

        # Check for obviously invalid coordinates (0,0 or repeated patterns)
        if lat == 0.0 and lng == 0.0:
            return False, "Invalid coordinates: (0,0) - GPS not acquired"

        # Check for repeated coordinate patterns that indicate GPS issues
        lat_str = str(lat)
        lng_str = str(lng)
        if (
            len(set(lat_str.replace(".", "").replace("-", ""))) <= 2
            or len(set(lng_str.replace(".", "").replace("-", ""))) <= 2
        ):
            return False, f"Suspicious coordinate pattern: lat={lat}, lng={lng}"

        return True, "Coordinate quality valid"

    def _validate_vehicle_parameters(self, vals: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate vehicle-specific parameters like engine temperature and fuel level.

        Args:
            vals: Dictionary of processed GPS values

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate engine temperature
        engine_temp = vals.get("engine_temperature", 0)
        if engine_temp and (engine_temp < self.MIN_ENGINE_TEMP or engine_temp > self.MAX_ENGINE_TEMP):
            return (
                False,
                f"Invalid engine temperature: {engine_temp}°C (range: {self.MIN_ENGINE_TEMP} to {self.MAX_ENGINE_TEMP}°C)",
            )

        # Validate fuel level
        fuel_level = vals.get("fuel_level", 0)
        if fuel_level and (fuel_level < 0 or fuel_level > 100):
            return False, f"Invalid fuel level: {fuel_level}% (range: 0-100%)"

        # Validate engine RPM
        engine_rpm = vals.get("engine_speed_rpm", 0)
        if engine_rpm and (engine_rpm < 0 or engine_rpm > 8000):
            return False, f"Invalid engine RPM: {engine_rpm} (range: 0-8000 RPM)"

        return True, "Vehicle parameters valid"

    def _validate_electrical_parameters(self, vals: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate electrical system parameters like voltage readings.

        Args:
            vals: Dictionary of processed GPS values

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate external voltage (vehicle battery)
        external_voltage = vals.get("external_voltage", 0)
        if external_voltage and (external_voltage < 6 or external_voltage > 30):
            return (
                False,
                f"Invalid external voltage: {external_voltage}V (typical range: 6-30V)",
            )

        # Validate internal battery voltage (device battery)
        battery_voltage = vals.get("battery_voltage", 0)
        if battery_voltage and (battery_voltage < 3 or battery_voltage > 5):
            return (
                False,
                f"Invalid battery voltage: {battery_voltage}V (typical range: 3-5V)",
            )

        # Validate battery current
        battery_current = vals.get("battery_current", 0)
        if battery_current and abs(battery_current) > 5000:  # 5A in mA
            return (
                False,
                f"Invalid battery current: {battery_current}mA (typical range: -5000 to 5000mA)",
            )

        return True, "Electrical parameters valid"

    def _validate_speed_parameters(
        self, vals: Dict[str, Any], device_id: int = None
    ) -> tuple[bool, str]:
        """
        Validate speed-related parameters including absolute speed and speed changes.

        Args:
            vals: Dictionary of processed GPS values
            device_id: GPS device ID for temporal speed change validation (optional)

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate absolute speed reasonableness
        speed = vals.get("speed", 0)
        if speed and speed > self.MAX_REASONABLE_SPEED:
            return (
                False,
                f"Unrealistic speed detected: {speed} km/h (maximum: {self.MAX_REASONABLE_SPEED})",
            )

        # Validate speed change rate if device_id is provided
        if device_id and speed:
            try:
                # Get the last GPS point for this device
                last_point = (
                    request.env["gps.tracking.point"]
                    .sudo()
                    .search(
                        [("device_id", "=", device_id)], order="timestamp desc", limit=1
                    )
                )

                if last_point and last_point.speed and vals.get("timestamp"):
                    time_diff = (
                        vals.get("timestamp") - last_point.timestamp
                    ).total_seconds()
                    time_minutes = abs(time_diff) / 60

                    if time_minutes > 0:
                        speed_change = abs(speed - last_point.speed)
                        speed_change_per_minute = speed_change / time_minutes

                        if speed_change_per_minute > self.MAX_SPEED_CHANGE_PER_MINUTE:
                            return (
                                False,
                                f"Unrealistic speed change: {speed_change:.1f} km/h in {time_minutes:.1f} minutes",
                            )
            except Exception as e:
                # Don't fail validation on speed change calculation errors
                pass

        return True, "Speed parameters valid"

    def _validate_temporal_sequence(
        self, device_id: int, new_timestamp: datetime
    ) -> tuple[bool, str]:
        """
        Validate temporal sequence focusing purely on time-based validations.

        Args:
            device_id: GPS device ID
            new_timestamp: Timestamp of new GPS point

        Returns:
            Tuple of (is_valid, warning_message)
        """
        try:
            # Get the last GPS point for this device
            last_point = (
                request.env["gps.tracking.point"]
                .sudo()
                .search(
                    [("device_id", "=", device_id)], order="timestamp desc", limit=1
                )
            )

            if not last_point:
                return True, "No previous point for comparison"

            # Check for duplicate timestamps
            time_diff = (new_timestamp - last_point.timestamp).total_seconds()
            if abs(time_diff) < 1:  # Less than 1 second difference
                return (
                    False,
                    f"Duplicate or too-close timestamp: {abs(time_diff):.1f}s from last point",
                )

            # Check for points too far in the future
            now = datetime.now()
            future_diff = (new_timestamp - now).total_seconds()
            if future_diff > 300:  # More than 5 minutes in the future
                return (
                    False,
                    f"Timestamp too far in future: {future_diff/60:.1f} minutes",
                )

            # Check for points too far in the past (more than 24 hours)
            if time_diff < -86400:  # More than 24 hours in the past
                return (
                    False,
                    f"Timestamp too far in past: {abs(time_diff/3600):.1f} hours ago",
                )

            return True, "Valid temporal sequence"

        except Exception as e:
            return True, "Temporal validation error - allowing point"

    def _is_duplicate_point(
        self,
        device_id: int,
        timestamp: datetime,
        latitude: float = None,
        longitude: float = None,
    ) -> bool:
        """
        Check for duplicate GPS points within time window.

        Args:
            device_id: GPS device ID
            timestamp: Point timestamp
            latitude: GPS latitude (optional)
            longitude: GPS longitude (optional)

        Returns:
            True if duplicate detected
        """
        try:
            # Define time window for duplicate detection
            time_window_start = timestamp - timedelta(
                seconds=self.MAX_DUPLICATE_TIME_WINDOW
            )
            time_window_end = timestamp + timedelta(
                seconds=self.MAX_DUPLICATE_TIME_WINDOW
            )

            # Search for points in the time window
            domain = [
                ("device_id", "=", device_id),
                ("timestamp", ">=", time_window_start),
                ("timestamp", "<=", time_window_end),
            ]

            # If coordinates provided, also check for spatial duplicates
            if latitude is not None and longitude is not None:
                # Allow small coordinate differences (about 1 meter precision)
                lat_tolerance = 0.00001
                lng_tolerance = 0.00001

                domain.extend(
                    [
                        ("latitude", ">=", latitude - lat_tolerance),
                        ("latitude", "<=", latitude + lat_tolerance),
                        ("longitude", ">=", longitude - lng_tolerance),
                        ("longitude", "<=", longitude + lng_tolerance),
                    ]
                )

            existing_points = (
                request.env["gps.tracking.point"].sudo().search(domain, limit=1)
            )

            if existing_points:

                return True

            return False

        except Exception as e:
            return False  # Don't block on validation errors
