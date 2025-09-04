import logging

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


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

    # Validation constraints
    MIN_TIMESTAMP = 946684800000  # Jan 1, 2000 in milliseconds
    MAX_TIMESTAMP = 2147483647000  # Jan 19, 2038 in milliseconds
    MIN_LATITUDE = -90.0
    MAX_LATITUDE = 90.0
    MIN_LONGITUDE = -180.0
    MAX_LONGITUDE = 180.0
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

            is_quality_valid, quality_error, device, vals = (
                self._validate_payload_quality(
                    payload,
                    processing_stats,
                )
            )

            # Extract IMEI from device for logging (if device was found)
            imei = device.imei if device else "unknown"

            if not is_quality_valid:
                self._log_webhook_failure(
                    start_time,
                    remote_addr,
                    imei,
                    f"Quality validation failed: {quality_error}",
                    processing_stats,
                )
                return self.RESPONSE_FAILURE

            processing_stats["validation_time"] = (
                datetime.now() - processing_stats["validation_start"]
            ).total_seconds()

            db_start_time = datetime.now()

            try:
                with request.env.cr.savepoint():
                    # Create tracking point within transaction
                    new_point = self._create_tracking_point(vals)
                    if not new_point:
                        raise Exception("Failed to create tracking point record")
                    # Update device's last point reference within same transaction
                    self._update_device_last_point(device, new_point.id)
                    processing_stats["db_operation_time"] = (
                        datetime.now() - db_start_time
                    ).total_seconds()
                msg = "Point processed successfully"
                self._log_webhook_success(
                    start_time,
                    remote_addr,
                    imei,
                    msg,
                    processing_stats,
                    vals,
                )
                return self.RESPONSE_SUCCESS

            except Exception as db_error:
                # Transaction automatically rolled back due to savepoint context
                processing_stats["db_operation_time"] = (
                    datetime.now() - db_start_time
                ).total_seconds()
                msg = f"Database transaction failed: {str(db_error)}"
                self._log_webhook_failure(
                    start_time,
                    remote_addr,
                    imei,
                    msg,
                    processing_stats,
                )
                return self.RESPONSE_FAILURE

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
        self, tracking_point_vals: Dict[str, Any], field_name: str, value: Any
    ) -> None:
        """
        Process individual field value based on field type

        Args:
            vals: Dictionary to store processed values
            field_name: Model field name
            value: Raw value from GPS data
        """
        try:
            if field_name == "latitude_longitude":
                lat, lng = self._process_latlong_coordinates(value)
                if lat is not None and lng is not None:
                    tracking_point_vals["latitude"] = lat
                    tracking_point_vals["longitude"] = lng

            elif field_name == "timestamp":
                processed_ts = self._process_timestamp(value)
                if processed_ts:
                    tracking_point_vals[field_name] = processed_ts

            elif field_name == "odometer":
                processed_odo = self._process_odometer(value)
                if processed_odo is not None:
                    tracking_point_vals[field_name] = processed_odo

            elif field_name == "engine_temperature":
                processed_et = self._process_engine_temperature(value)
                if processed_et is not None:
                    tracking_point_vals[field_name] = processed_et

            else:
                # Store value directly for other fields
                tracking_point_vals[field_name] = value

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
        tracking_point_vals = {"device_id": device_id}
        tracking_point_model = request.env["gps.tracking.point"].sudo()
        available_fields = set(tracking_point_model._fields.keys())

        # Process each mapped field
        for iot_field, model_field in self.FIELD_MAPPING.items():
            if iot_field not in payload:
                continue

            if model_field not in available_fields:
                continue

            value = payload[iot_field]
            if value is not None:
                self._process_field_value(tracking_point_vals, model_field, value)

        return tracking_point_vals

    @classmethod
    def _get_validation_config(cls, force_reload=False):
        """
        Centralized configuration loading with class-level caching to persist across requests.

        Args:
            force_reload: Force reload configuration from database

        Returns:
            dict: All validation parameters loaded once and cached at class level
        """
        if force_reload or not hasattr(cls, "_validation_config_cache"):
            try:
                param_obj = request.env["ir.config_parameter"].sudo()
                cls._validation_config_cache = {
                    # GPS accuracy parameters
                    "min_satellites": int(
                        param_obj.get_param(
                            "gps_tracking.validation.min_satellites",
                            default=cls.MIN_SATELLITES_FOR_ACCURACY,
                        )
                    ),
                    "max_hdop": float(
                        param_obj.get_param(
                            "gps_tracking.validation.max_hdop",
                            default=5.0,
                        )
                    ),
                    # Coordinate parameters
                    "min_latitude": float(
                        param_obj.get_param(
                            "gps_tracking.validation.min_latitude",
                            default=cls.MIN_LATITUDE,
                        )
                    ),
                    "max_latitude": float(
                        param_obj.get_param(
                            "gps_tracking.validation.max_latitude",
                            default=cls.MAX_LATITUDE,
                        )
                    ),
                    "min_longitude": float(
                        param_obj.get_param(
                            "gps_tracking.validation.min_longitude",
                            default=cls.MIN_LONGITUDE,
                        )
                    ),
                    "max_longitude": float(
                        param_obj.get_param(
                            "gps_tracking.validation.max_longitude",
                            default=cls.MAX_LONGITUDE,
                        )
                    ),
                    "zero_tolerance": float(
                        param_obj.get_param(
                            "gps_tracking.validation.zero_coordinate_tolerance",
                            default=0.001,
                        )
                    ),
                    # Vehicle parameters
                    "max_realistic_speed": float(
                        param_obj.get_param(
                            "gps_tracking.validation.max_realistic_speed",
                            default=cls.MAX_REASONABLE_SPEED,
                        )
                    ),
                    "max_fuel_level": float(
                        param_obj.get_param(
                            "gps_tracking.validation.max_fuel_level",
                            default=100.0,
                        )
                    ),
                    "max_engine_hours": int(
                        param_obj.get_param(
                            "gps_tracking.validation.max_engine_hours",
                            default=50000,
                        )
                    ),
                    # Electrical parameters
                    "min_external_voltage": float(
                        param_obj.get_param(
                            "gps_tracking.validation.min_external_voltage",
                            default=8.0,
                        )
                    ),
                    "max_external_voltage": float(
                        param_obj.get_param(
                            "gps_tracking.validation.max_external_voltage",
                            default=30.0,
                        )
                    ),
                    "min_internal_voltage": float(
                        param_obj.get_param(
                            "gps_tracking.validation.min_internal_voltage",
                            default=2.5,
                        )
                    ),
                    "max_internal_voltage": float(
                        param_obj.get_param(
                            "gps_tracking.validation.max_internal_voltage",
                            default=5.5,
                        )
                    ),
                    "min_gsm_signal": int(
                        param_obj.get_param(
                            "gps_tracking.validation.min_gsm_signal", default=0
                        )
                    ),
                    "max_gsm_signal": int(
                        param_obj.get_param(
                            "gps_tracking.validation.max_gsm_signal", default=31
                        )
                    ),
                    # Speed change parameters
                    "max_speed_change": float(
                        param_obj.get_param(
                            "gps_tracking.validation.max_speed_change_kmh_per_sec",
                            default=10.0,
                        )
                    ),
                    "speed_window_seconds": int(
                        param_obj.get_param(
                            "gps_tracking.validation.speed_validation_window_seconds",
                            default=30,
                        )
                    ),
                    # Temporal parameters
                    "max_time_gap_hours": float(
                        param_obj.get_param(
                            "gps_tracking.validation.max_time_gap_hours",
                            default=24.0,
                        )
                    ),
                    "min_time_interval_seconds": int(
                        param_obj.get_param(
                            "gps_tracking.validation.min_time_interval_seconds",
                            default=1,
                        )
                    ),
                    # Duplicate detection parameters
                    "duplicate_time_window": int(
                        param_obj.get_param(
                            "gps_tracking.validation.duplicate_time_window_seconds",
                            default=10,
                        )
                    ),
                    "coordinate_tolerance": float(
                        param_obj.get_param(
                            "gps_tracking.validation.duplicate_coordinate_tolerance",
                            default=0.00001,
                        )
                    ),
                    "extended_window": int(
                        param_obj.get_param(
                            "gps_tracking.validation.duplicate_extended_window_seconds",
                            default=300,
                        )
                    ),
                }
                _logger.info(
                    "Validation configuration loaded successfully with %d parameters",
                    len(cls._validation_config_cache),
                )
            except Exception as e:
                _logger.error("Failed to load validation config: %s", e)
                # Return minimal safe defaults if loading fails
                cls._validation_config_cache = {
                    "min_satellites": cls.MIN_SATELLITES_FOR_ACCURACY,
                    "max_hdop": 5.0,
                    "min_latitude": cls.MIN_LATITUDE,
                    "max_latitude": cls.MAX_LATITUDE,
                    "min_longitude": cls.MIN_LONGITUDE,
                    "max_longitude": cls.MAX_LONGITUDE,
                    "zero_tolerance": 0.001,
                    "max_realistic_speed": cls.MAX_REASONABLE_SPEED,
                    "max_fuel_level": 100.0,
                    "max_engine_hours": 50000,
                    "min_external_voltage": 8.0,
                    "max_external_voltage": 30.0,
                    "min_internal_voltage": 2.5,
                    "max_internal_voltage": 5.5,
                    "min_gsm_signal": 0,
                    "max_gsm_signal": 31,
                    "max_speed_change": 10.0,
                    "speed_window_seconds": 30,
                    "max_time_gap_hours": 24.0,
                    "min_time_interval_seconds": 1,
                    "duplicate_time_window": 10,
                    "coordinate_tolerance": 0.00001,
                    "extended_window": 300,
                }
        return cls._validation_config_cache

    @classmethod
    def _clear_validation_cache(cls):
        """Clear validation configuration cache (useful when settings change)."""
        if hasattr(cls, "_validation_config_cache"):
            delattr(cls, "_validation_config_cache")
            _logger.info("Validation configuration cache cleared")

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

    @classmethod
    def _get_recent_points_cache(cls, device_id: int, window_seconds: int = None):
        """
        Cache recent GPS points to eliminate duplicate database queries with class-level persistence.

        Used by speed validation, temporal validation, and duplicate detection.

        Args:
            device_id: GPS device ID
            window_seconds: Time window for recent points (uses config if None)

        Returns:
            Recordset of recent GPS points
        """
        if not hasattr(cls, "_points_cache"):
            cls._points_cache = {}

        # Use configuration for window if not specified
        if window_seconds is None:
            config = cls._get_validation_config()
            window_seconds = config.get("extended_window", 300)

        cache_key = f"recent_points_{device_id}_{window_seconds}"

        # Simple cache without TTL for now (points are relatively stable within request)
        if cache_key not in cls._points_cache:
            try:
                cutoff_time = datetime.now() - timedelta(seconds=window_seconds)
                recent_points = (
                    request.env["gps.tracking.point"]
                    .sudo()
                    .search(
                        [
                            ("device_id", "=", device_id),
                            ("timestamp", ">=", cutoff_time),
                        ],
                        order="timestamp desc",
                        limit=10,
                    )
                )
                cls._points_cache[cache_key] = recent_points
                _logger.debug(
                    "Cached %d recent points for device %d",
                    len(recent_points),
                    device_id,
                )
            except Exception as e:
                _logger.error(
                    "Error caching recent points for device %d: %s", device_id, e
                )
                return request.env["gps.tracking.point"].sudo().browse([])

        return cls._points_cache[cache_key]

    @classmethod
    def _clear_points_cache(cls):
        """Clear points cache (useful for tests or when points change significantly)."""
        if hasattr(cls, "_points_cache"):
            cls._points_cache.clear()
            _logger.debug("Points cache cleared")

    # ------------------------------------------------------------
    # DATA PROCESING METHODS
    # ------------------------------------------------------------

    def _process_latlong_coordinates(
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
            # Basic range check for timestamp (avoid circular dependency)
            if not isinstance(timestamp_ms, (int, float)) or timestamp_ms <= 0:
                return None

            # Check reasonable bounds (year 2000 to 2040)
            if timestamp_ms < self.MIN_TIMESTAMP or timestamp_ms > self.MAX_TIMESTAMP:
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

    def _validate_payload_quality(
        self,
        payload: Dict[str, Any],
        processing_stats: Dict[str, Any],
    ) -> tuple[bool, str, Any, Dict[str, Any]]:
        """
        Optimized comprehensive GPS data quality validation with configurable severity levels.

        Eliminates redundant parameter loading and database queries through caching.

        Args:
            payload: Dictionary of processed GPS values
            processing_stats: Processing statistics dictionary to track validation results

        Returns:
            Tuple of (is_valid, error_message, device, vals)
        """
        # Load all validation configuration once (replaces 23+ individual parameter loads)
        config = self.__class__._get_validation_config()

        # Collect errors and warnings with configurable severity
        # Cache recent points for multiple validations (replaces 3+ duplicate queries)
        errors = []
        warnings = []
        vals = {}
        device = None
        recent_points = None

        # Define validation rules with severity levels
        validation_rules = [
            (
                "prerequisite_validation",
                self._validate_prerequisites,
                "critical",
            ),
            (
                "timestamp_quality",
                self._validate_timestamp,
                "critical",
            ),
            (
                "coordinate_quality",
                self._validate_coordinates,
                "critical",
            ),
            (
                "gps_accuracy",
                self._validate_gps_accuracy,
                "warning",
            ),
            (
                "comprehensive_parameters",
                self._validate_comprehensive_parameters,
                "warning",
            ),
            (
                "speed_parameters",
                self._validate_speed_parameters,
                "warning",
            ),
            (
                "record_duplication",
                self.validate_record_duplication,
                "critical",
            ),
        ]

        for rule_name, validator_func, severity in validation_rules:
            try:
                # Pass validation context for prerequisite validation
                if rule_name == "prerequisite_validation":
                    is_valid, message, device = validator_func(payload)
                    # Prepare tracking point values (using device.id if device exists)
                else:
                    is_valid, message = validator_func(vals, config, recent_points)

                if is_valid:
                    processing_stats["quality_checks_passed"] += 1
                    if rule_name == "prerequisite_validation":
                        # Prepare tracking point values (using device.id if device exists)
                        vals = self._prepare_tracking_point_vals(device.id, payload)
                        recent_points = self.__class__._get_recent_points_cache(
                            device.id
                        )
                elif not is_valid:
                    processing_stats["quality_checks_failed"] += 1
                    if severity == "critical":
                        errors.append(f"{rule_name}: {message}")
                        continue
                    elif severity == "warning":
                        warnings.append(f"{rule_name}: {message}")

            except Exception as e:
                # Count exceptions as failed checks
                processing_stats["quality_checks_failed"] += 1
                imei_info = vals.get("imei", payload.get("14", "unknown"))
                _logger.error(
                    "Validation exception in rule '%s' for device %s: %s",
                    rule_name,
                    imei_info,
                    str(e),
                    exc_info=True,
                )
                # Treat validation exceptions as critical errors to ensure data integrity
                errors.append(f"{rule_name}: Validation failed due to system error")

        # Return failure only for critical errors
        if errors:
            imei_info = (
                vals.get("imei", payload.get("14", "unknown"))
                if vals
                else payload.get("14", "unknown")
            )
            error_summary = (
                f"Validation failed for device {imei_info}: {'; '.join(errors)}"
            )
            _logger.warning("GPS validation failed: %s", error_summary)
            return False, error_summary, device, vals

        # Log warnings but don't fail validation
        if warnings:
            imei_info = device.imei if device else payload.get("14", "unknown")
            warning_summary = (
                f"GPS validation warnings for device {imei_info}: {'; '.join(warnings)}"
            )
            _logger.info(warning_summary)

        passed_checks = processing_stats.get("quality_checks_passed", 0)
        total_checks = passed_checks + processing_stats.get("quality_checks_failed", 0)
        success_message = (
            f"Validation successful: {passed_checks}/{total_checks} checks passed"
        )

        return True, success_message, device, vals

    def _validate_prerequisites(self, payload: Dict[str, Any]) -> tuple[bool, str, Any]:
        """
        Critical prerequisite validation for IMEI and device existence.

        Args:
            payload: GPS data payload containing IMEI and other fields

        Returns:
            Tuple of (is_valid, error_message, device)
        """
        imei = payload.get("14")
        # Validate IMEI exists in payload
        if not imei:
            _logger.warning("No IMEI found in payload")
            return False, "Missing IMEI in GPS data", None

        device = self._get_device(imei)
        # Validate device exists in database
        if not device:
            _logger.warning("No device found in database for IMEI %s", imei)
            return False, f"Device not found for IMEI: {imei}", None

        return True, "Prerequisites valid", device

    def _validate_range(self, value, min_val, max_val, param_name: str, unit: str = ""):
        """
        Generic range validation helper to eliminate duplicate validation patterns.

        Args:
            value: Value to validate
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            param_name: Parameter name for error messages
            unit: Unit suffix for error messages

        Returns:
            Tuple of (is_valid, error_message)
        """
        if value is None or value == 0:
            return True, f"No {param_name} to validate"

        if not (min_val <= value <= max_val):
            return (
                False,
                f"Invalid {param_name}: {value}{unit} (range: {min_val}-{max_val}{unit})",
            )

        return True, f"{param_name} valid"

    def _validate_timestamp(
        self, vals: Dict[str, Any], config: dict, recent_points=None
    ) -> tuple[bool, str]:
        """
        Critical timestamp validation using cached config.

        Args:
            vals: Dictionary of processed GPS values
            config: Pre-loaded validation configuration

        Returns:
            Tuple of (is_valid, error_message)
        """
        timestamp = vals.get("timestamp")

        # Check if timestamp exists
        if not timestamp:
            return False, "Missing timestamp in GPS data"

        # Validate timestamp is datetime object
        if not isinstance(timestamp, datetime):
            return (
                False,
                f"Invalid timestamp type: expected datetime, got {type(timestamp).__name__}",
            )

        # Check timestamp bounds (not too far in past/future)
        now = datetime.now()
        time_diff = (timestamp - now).total_seconds()

        # Check for future timestamps (more than 5 minutes ahead)
        if time_diff > 300:  # 5 minutes
            return (
                False,
                f"Timestamp too far in future: {time_diff/60:.1f} minutes ahead",
            )

        # Check for very old timestamps (more than configured max time gap)
        max_past_hours = config.get("max_time_gap_hours", 24)
        max_past_seconds = max_past_hours * 3600

        if time_diff < -max_past_seconds:
            return (
                False,
                f"Timestamp too old: {abs(time_diff/3600):.1f} hours ago (maximum: {max_past_hours} hours)",
            )

        # Check for minimum realistic timestamp (year 2000+)
        min_year_2000 = datetime(2000, 1, 1)
        if timestamp < min_year_2000:
            return (
                False,
                f"Timestamp before year 2000: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            )

        return True, "Timestamp quality valid"

    def _validate_coordinates(
        self, vals: Dict[str, Any], config: dict, recent_points=None
    ) -> tuple[bool, str]:
        """
        Optimized coordinate validation using pre-loaded config and generic range validator.

        Args:
            vals: Dictionary of processed GPS values
            config: Pre-loaded validation configuration

        Returns:
            Tuple of (is_valid, error_message)
        """
        lat = vals.get("latitude")
        lng = vals.get("longitude")

        if lat is None or lng is None:
            return True, "No coordinates to validate"

        # Use cached config and generic range validator
        is_valid, msg = self._validate_range(
            lat, config["min_latitude"], config["max_latitude"], "latitude"
        )
        if not is_valid:
            return False, msg

        is_valid, msg = self._validate_range(
            lng, config["min_longitude"], config["max_longitude"], "longitude"
        )
        if not is_valid:
            return False, msg

        # Check for suspicious zero coordinates
        if abs(lat) < config["zero_tolerance"] and abs(lng) < config["zero_tolerance"]:
            return (
                False,
                f"Suspicious zero coordinates detected: lat={lat:.6f}, lng={lng:.6f} (tolerance: {config['zero_tolerance']})",
            )

        # Check for obviously invalid coordinates (0,0)
        if lat == 0.0 and lng == 0.0:
            return (
                False,
                "Invalid null coordinates (0.0, 0.0) - GPS signal not acquired",
            )

        return True, f"Coordinates valid: ({lat:.6f}, {lng:.6f})"

    def _validate_gps_accuracy(
        self, vals: Dict[str, Any], config: dict, recent_points=None
    ) -> tuple[bool, str]:
        """
        Optimized GPS accuracy validation using pre-loaded config.

        Args:
            vals: Dictionary of processed GPS values
            config: Pre-loaded validation configuration

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check GPS accuracy based on satellite count
        satellites = vals.get("satellites", 0)
        if satellites and satellites < config["min_satellites"]:
            return (
                False,
                f"Low GPS accuracy: only {satellites} satellites (minimum: {config['min_satellites']})",
            )

        # Check HDOP if available
        hdop = vals.get("gnss_hdop", 0)
        if hdop and hdop > config["max_hdop"]:
            return (
                False,
                f"Poor GPS precision: HDOP {hdop} exceeds maximum {config['max_hdop']}",
            )

        return True, "GPS accuracy valid"

    def _validate_comprehensive_parameters(
        self, vals: Dict[str, Any], config: dict, recent_points=None
    ) -> tuple[bool, str]:
        """
        Consolidated validation for vehicle, electrical, and network parameters.

        Replaces separate _validate_vehicle_parameters, _validate_electrical_parameters,
        and _validate_network_parameters functions to eliminate redundancy.

        Args:
            vals: Dictionary of processed GPS values
            config: Pre-loaded validation configuration

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Vehicle parameter validations
        is_valid, msg = self._validate_range(
            vals.get("fuel_level", 0),
            0,
            config["max_fuel_level"],
            "fuel level",
            "%",
        )
        if (
            not is_valid and vals.get("fuel_level", 0) > 0
        ):  # Only validate if fuel level provided
            return False, msg

        is_valid, msg = self._validate_range(
            vals.get("engine_total_hours", 0),
            0,
            config["max_engine_hours"],
            "engine hours",
        )
        if not is_valid and vals.get("engine_total_hours", 0) > 0:
            return False, msg

        # Speed validation (basic range, not change rate)
        is_valid, msg = self._validate_range(
            vals.get("speed", 0),
            0,
            config["max_realistic_speed"],
            "speed",
            " km/h",
        )
        if not is_valid and vals.get("speed", 0) > 0:
            return False, msg

        # Engine RPM validation
        engine_rpm = vals.get("engine_speed_rpm", 0)
        if engine_rpm and (engine_rpm < 0 or engine_rpm > 8000):
            return False, f"Invalid engine RPM: {engine_rpm} (range: 0-8000 RPM)"

        # Electrical parameter validations
        is_valid, msg = self._validate_range(
            vals.get("external_voltage", 0),
            config["min_external_voltage"],
            config["max_external_voltage"],
            "external voltage",
            "V",
        )
        if not is_valid and vals.get("external_voltage", 0) > 0:
            return False, msg

        is_valid, msg = self._validate_range(
            vals.get("battery_voltage", 0),
            config["min_internal_voltage"],
            config["max_internal_voltage"],
            "battery voltage",
            "V",
        )
        if not is_valid and vals.get("battery_voltage", 0) > 0:
            return False, msg

        # Battery current validation
        battery_current = vals.get("battery_current", 0)
        if battery_current and abs(battery_current) > 5000:  # 5A in mA
            return (
                False,
                f"Invalid battery current: {battery_current}mA (typical range: -5000 to 5000mA)",
            )

        # Network parameter validations
        is_valid, msg = self._validate_range(
            vals.get("gsm_signal", 0),
            config["min_gsm_signal"],
            config["max_gsm_signal"],
            "GSM signal",
        )
        if not is_valid and vals.get("gsm_signal", 0) > 0:
            return False, msg

        return True, "Comprehensive parameters valid"

    def _validate_speed_parameters(
        self, vals: Dict[str, Any], config: dict, recent_points
    ) -> tuple[bool, str]:
        """
        Optimized speed validation using cached recent points and config.

        Args:
            vals: Dictionary of processed GPS values
            config: Pre-loaded validation configuration
            recent_points: Cached recent points for speed change validation

        Returns:
            Tuple of (is_valid, error_message)
        """
        speed = vals.get("speed", 0)

        # Basic validation (negative speed check - positive range already done in comprehensive)
        if speed < 0:
            return False, f"Invalid negative speed: {speed} km/h"

        # Speed change validation using cached recent points
        if recent_points and speed and vals.get("timestamp"):
            last_point = recent_points[0] if recent_points else None
            if last_point and last_point.speed:
                time_diff = (
                    vals.get("timestamp") - last_point.timestamp
                ).total_seconds()

                # Only validate if within the validation window
                if 0 < abs(time_diff) <= config["speed_window_seconds"]:
                    speed_change = abs(speed - last_point.speed)
                    speed_change_per_second = speed_change / abs(time_diff)

                    if speed_change_per_second > config["max_speed_change"]:
                        return (
                            False,
                            f"Unrealistic speed change: {speed_change:.1f} km/h in {abs(time_diff):.1f} seconds",
                        )

        return True, "Speed parameters valid"

    def validate_record_duplication(
        self, vals: Dict[str, Any], config: dict, recent_points
    ) -> tuple[bool, str]:
        """
        Optimized duplicate detection using cached config and recent points.

        Args:
            vals: Dictionary of processed GPS values
            config: Pre-loaded validation configuration
            recent_points: Cached recent points for speed change validation

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Quick in-memory check against cached points first (fastest)
            for point in recent_points:
                time_diff = abs((vals["timestamp"] - point.timestamp).total_seconds())
                if time_diff <= config["duplicate_time_window"]:
                    if (
                        abs(point.latitude - vals["latitude"])
                        <= config["coordinate_tolerance"]
                        and abs(point.longitude - vals["longitude"])
                        <= config["coordinate_tolerance"]
                    ):
                        return False, "Duplicate point detected within time window"

            return True, "No duplicate found"

        except Exception as e:
            _logger.warning("Error in duplicate detection: %s", e)
            return (False, "Some error occurred during duplicate detection")
