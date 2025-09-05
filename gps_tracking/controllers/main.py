import logging

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple, Union, ClassVar, TypedDict

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
    RESPONSE_SUCCESS: ClassVar[bytes] = b"\x01"
    RESPONSE_FAILURE: ClassVar[bytes] = b"\x00"

    # Field mapping from GPS data to model fields
    FIELD_MAPPING: ClassVar[Dict[str, str]] = {
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
    MIN_TIMESTAMP: ClassVar[int] = 946684800000  # Jan 1, 2000 in milliseconds
    MAX_TIMESTAMP: ClassVar[int] = 2147483647000  # Jan 19, 2038 in milliseconds
    MIN_LATITUDE: ClassVar[float] = -90.0
    MAX_LATITUDE: ClassVar[float] = 90.0
    MIN_LONGITUDE: ClassVar[float] = -180.0
    MAX_LONGITUDE: ClassVar[float] = 180.0
    MIN_SATELLITES_FOR_ACCURACY: ClassVar[int] = (
        4  # Minimum satellites for good GPS accuracy
    )
    MAX_REASONABLE_SPEED: ClassVar[int] = (
        300  # Maximum reasonable speed in km/h for ground vehicles
    )
    MIN_COORDINATE_PRECISION: ClassVar[int] = (
        5  # Minimum decimal places for coordinates
    )
    MAX_DUPLICATE_TIME_WINDOW: ClassVar[int] = (
        15  # Seconds to check for duplicate points
    )
    MAX_SPEED_CHANGE_PER_MINUTE: ClassVar[int] = (
        100  # km/h - detect unrealistic speed changes
    )
    MIN_ENGINE_TEMP: ClassVar[int] = -40  # °C
    MAX_ENGINE_TEMP: ClassVar[int] = 150  # °C

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
        and stores tracking points in the database with full transaction safety.

        Flow:
        1. Extract and validate JSON payload
        2. Find device by IMEI
        3. Process and validate GPS data fields
        4. Perform data quality validation
        5. Check for duplicates and temporal sequence
        6. Create tracking point record
        7. Update device's last known position

        Args:
            **kwargs: HTTP request parameters (automatically handled by Odoo)

        Returns:
            bytes: Success (0x01) or failure (0x00) response byte for IoT device

        Side Effects:
            - Creates gps.tracking.point records
            - Updates device last_point_id reference
            - Logs comprehensive metrics and errors
            - Modifies processing_stats dictionary

        Raises:
            Exception: All exceptions are caught and logged, returns failure response

        Performance:
            Tracks validation time, database operation time, and quality metrics
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
            json_data = request.get_json_data()
            if not json_data:
                _logger.warning("Empty JSON data received")
                return self.RESPONSE_FAILURE

            payload = self._extract_payload(json_data)
            if not payload:
                return self.RESPONSE_FAILURE

            is_valid, error, device, vals = self._validate_payload(
                payload,
                processing_stats,
            )

            if not is_valid:
                self._log_webhook_result(
                    start_time,
                    remote_addr,
                    device.imei if device else "unknown",
                    f"Quality validation failed: {error}",
                    processing_stats,
                    vals,
                    is_success=False,
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
                self._log_webhook_result(
                    start_time,
                    remote_addr,
                    imei,
                    msg,
                    processing_stats,
                    vals,
                    is_success=True,
                )
                return self.RESPONSE_SUCCESS

            except Exception as db_error:
                # Transaction automatically rolled back due to savepoint context
                processing_stats["db_operation_time"] = (
                    datetime.now() - db_start_time
                ).total_seconds()
                msg = f"Database transaction failed: {str(db_error)}"
                self._log_webhook_result(
                    start_time,
                    remote_addr,
                    imei,
                    msg,
                    processing_stats,
                    vals,
                    is_success=False,
                )
                return self.RESPONSE_FAILURE

        except Exception as e:
            self._log_webhook_result(
                start_time,
                remote_addr,
                imei,
                f"Unexpected error: {str(e)}",
                processing_stats,
                vals=None,
                is_success=False,
            )
            return self.RESPONSE_FAILURE

    # ------------------------------------------------------------
    # LOGGING HELPERS
    # ------------------------------------------------------------

    def _log_webhook_result(
        self,
        start_time: datetime,
        remote_addr: str,
        imei: str,
        message: str,
        processing_stats: dict,
        vals: dict = None,
        is_success: bool = True,
    ):
        """
        Unified webhook logging with comprehensive metrics for both success and failure.

        Args:
            start_time: Request start time
            remote_addr: Remote IP address
            imei: Device IMEI
            message: Success message or error description
            processing_stats: Processing performance statistics
            vals: GPS values dictionary (optional, provides debugging info even for failures)
            is_success: True for success, False for failure
        """
        total_duration = (datetime.now() - start_time).total_seconds()

        # Prepare quality metrics for debugging (available for both success and failure)
        quality_metrics = {}
        if vals:
            quality_metrics = {
                "satellites": vals.get("satellites", "N/A"),
                "speed": vals.get("speed", "N/A"),
                "fuel_level": vals.get("fuel_level", "N/A"),
                "engine_temp": vals.get("engine_temperature", "N/A"),
                "coordinates": f"({vals.get('latitude', 'N/A')}, {vals.get('longitude', 'N/A')})",
                "timestamp": vals.get("timestamp", "N/A"),
                "device_id": vals.get("device_id", "N/A"),
            }

        # Common log format for both success and failure
        status = "SUCCESS" if is_success else "FAILURE"
        log_method = _logger.info if is_success else _logger.error

        log_method(
            "GPS_WEBHOOK_%s device=%s ip=%s duration=%.3fs validation=%.3fs db=%.3fs "
            "quality_passed=%d quality_failed=%d message='%s' metrics=%s",
            status,
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
        Process individual field value based on field type.

        Handles special field processing including coordinate parsing,
        timestamp conversion, and unit conversions. Modifies the
        tracking_point_vals dictionary in place.

        Args:
            tracking_point_vals: Dictionary to store processed values (modified in-place)
            field_name: Model field name from FIELD_MAPPING
            value: Raw value from GPS data payload

        Special Processing:
            - latitude_longitude: Parses comma-separated coordinates
            - timestamp: Converts milliseconds to datetime
            - odometer: Converts meters to kilometers
            - engine_temperature: Converts decigrades to degrees

        Raises:
            Exception: Logs warning for processing failures but continues execution
        """
        try:
            if field_name == "latitude_longitude":
                lat, lng = self._process_latlong_coordinates(value)
                tracking_point_vals["latitude"] = lat
                tracking_point_vals["longitude"] = lng

            elif field_name == "timestamp":
                processed_ts = self._process_timestamp(value)
                tracking_point_vals[field_name] = processed_ts

            elif field_name == "odometer":
                processed_odo = self._process_odometer(value)
                tracking_point_vals[field_name] = processed_odo

            elif field_name == "engine_temperature":
                processed_et = self._process_engine_temperature(value)
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
        Prepare values for creating tracking point record.

        Maps GPS data payload fields to model fields using FIELD_MAPPING,
        applies field validation, and handles composite fields that map
        to multiple model fields.

        Args:
            device_id: ID of the GPS device
            payload: GPS data payload containing raw IoT field values

        Returns:
            Dictionary of field values ready for gps.tracking.point creation

        Note:
            Composite fields (like latitude_longitude) are processed specially
            and map to multiple model fields (latitude + longitude)
        """
        tracking_point_vals = {"device_id": device_id}
        tracking_point_model = request.env["gps.tracking.point"].sudo()
        available_fields = set(tracking_point_model._fields.keys())

        # Define composite fields that map to multiple model fields
        composite_field = {"latitude_longitude"}

        # Process each mapped field
        for iot_field, model_field in self.FIELD_MAPPING.items():
            if iot_field not in payload:
                continue

            # Skip field validation for composite fields (they map to multiple fields)
            if (
                model_field not in composite_field
                and model_field not in available_fields
            ):
                continue

            value = payload[iot_field]
            if value is not None:
                self._process_field_value(tracking_point_vals, model_field, value)

        return tracking_point_vals

    @classmethod
    def _get_validation_config(cls, force_reload: bool = False):
        """
        Centralized configuration loading with class-level caching to persist across requests.

        Loads GPS validation parameters from system configuration with descriptive,
        hierarchical parameter names for better administration experience.

        Args:
            force_reload: Force reload configuration from database

        Returns:
            dict: All validation parameters loaded once and cached at class level

        Parameter Categories:
            - geographic_bounds.*: Geographic coordinate validation limits
            - signal_quality.*: GPS signal strength and accuracy requirements
            - vehicle_limits.*: Vehicle operation parameter bounds
            - power_systems.*: Voltage and battery validation ranges
            - communication.*: GSM signal strength validation
            - movement_analysis.*: Speed change and movement validation
            - timestamp_validation.*: Time-based validation rules
            - duplicate_detection.*: Duplicate point detection settings
        """
        if force_reload or not hasattr(cls, "_validation_config_cache"):
            try:
                param_obj = request.env["ir.config_parameter"].sudo()
                cls._validation_config_cache = {
                    # Geographic Boundary Parameters
                    "min_latitude": float(
                        param_obj.get_param(
                            "gps_tracking.min_allowed_latitude_degrees",
                            default=cls.MIN_LATITUDE,
                        )
                    ),
                    "max_latitude": float(
                        param_obj.get_param(
                            "gps_tracking.geographic_bounds.max_allowed_latitude_degrees",
                            default=cls.MAX_LATITUDE,
                        )
                    ),
                    "min_longitude": float(
                        param_obj.get_param(
                            "gps_tracking.geographic_bounds.min_allowed_longitude_degrees",
                            default=cls.MIN_LONGITUDE,
                        )
                    ),
                    "max_longitude": float(
                        param_obj.get_param(
                            "gps_tracking.geographic_bounds.max_allowed_longitude_degrees",
                            default=cls.MAX_LONGITUDE,
                        )
                    ),
                    # GPS Signal Quality Parameters
                    "min_satellites": int(
                        param_obj.get_param(
                            "gps_tracking.min_required_satellites_count",
                            default=cls.MIN_SATELLITES_FOR_ACCURACY,
                        )
                    ),
                    "max_hdop": float(
                        param_obj.get_param(
                            "gps_tracking.signal_quality.max_acceptable_hdop_value",
                            default=5.0,
                        )
                    ),
                    # Vehicle Operation Limits
                    "max_realistic_speed": float(
                        param_obj.get_param(
                            "gps_tracking.vehicle_limits.max_realistic_speed_kmh",
                            default=cls.MAX_REASONABLE_SPEED,
                        )
                    ),
                    "max_fuel_level": float(
                        param_obj.get_param(
                            "gps_tracking.vehicle_limits.max_fuel_level_percentage",
                            default=100.0,
                        )
                    ),
                    "max_engine_hours": int(
                        param_obj.get_param(
                            "gps_tracking.vehicle_limits.max_engine_total_hours",
                            default=50000,
                        )
                    ),
                    # Power and Communication Systems
                    "min_external_voltage": float(
                        param_obj.get_param(
                            "gps_tracking.power_systems.min_external_voltage_volts",
                            default=8.0,
                        )
                    ),
                    "max_external_voltage": float(
                        param_obj.get_param(
                            "gps_tracking.power_systems.max_external_voltage_volts",
                            default=30.0,
                        )
                    ),
                    "min_internal_voltage": float(
                        param_obj.get_param(
                            "gps_tracking.power_systems.min_battery_voltage_volts",
                            default=2.5,
                        )
                    ),
                    "max_internal_voltage": float(
                        param_obj.get_param(
                            "gps_tracking.power_systems.max_battery_voltage_volts",
                            default=5.5,
                        )
                    ),
                    "min_gsm_signal": int(
                        param_obj.get_param(
                            "gps_tracking.communication.min_gsm_signal_strength",
                            default=0,
                        )
                    ),
                    "max_gsm_signal": int(
                        param_obj.get_param(
                            "gps_tracking.communication.max_gsm_signal_strength",
                            default=31,
                        )
                    ),
                    # Movement Analysis Parameters
                    "max_speed_change": float(
                        param_obj.get_param(
                            "gps_tracking.movement_analysis.max_speed_change_kmh_per_second",
                            default=10.0,
                        )
                    ),
                    "speed_window_seconds": int(
                        param_obj.get_param(
                            "gps_tracking.movement_analysis.speed_validation_window_seconds",
                            default=30,
                        )
                    ),
                    # Timestamp Validation Rules
                    "max_time_past_hours": float(
                        param_obj.get_param(
                            "gps_tracking.timestamp_validation.max_acceptable_past_hours",
                            default=24.0,
                        )
                    ),
                    "max_time_future_minutes": float(
                        param_obj.get_param(
                            "gps_tracking.timestamp_validation.max_acceptable_future_minutes",
                            default=5.0,
                        )
                    ),
                    "min_time_interval_seconds": int(
                        param_obj.get_param(
                            "gps_tracking.timestamp_validation.min_time_interval_between_points",
                            default=1,
                        )
                    ),
                    # Duplicate Point Detection Settings
                    "duplicate_time_window": int(
                        param_obj.get_param(
                            "gps_tracking.duplicate_detection.time_window_seconds",
                            default=15,
                        )
                    ),
                    "coordinate_tolerance": float(
                        param_obj.get_param(
                            "gps_tracking.duplicate_detection.coordinate_tolerance_degrees",
                            default=0.00001,
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
                    "max_time_past_hours": 24.0,
                    "max_time_future_minutes": 5.0,
                    "min_time_interval_seconds": 1,
                    "duplicate_time_window": 15,
                    "coordinate_tolerance": 0.00001,
                }
        return cls._validation_config_cache

    @classmethod
    def _clear_validation_cache(cls):
        """
        Clear validation configuration cache to force reload from database.

        This method should be called when validation parameters are updated
        in the system configuration to ensure the next request uses fresh values.
        Useful for dynamic configuration updates without server restart.

        Usage scenarios:
        - After updating GPS validation settings in admin interface
        - During system maintenance or configuration changes
        - When implementing configuration hot-reload functionality

        Note:
            Cache is automatically recreated on next _get_validation_config() call
        """
        if hasattr(cls, "_validation_config_cache"):
            delattr(cls, "_validation_config_cache")
            _logger.info("Validation configuration cache cleared")

    # ------------------------------------------------------------
    # DATABASE OPERATIONS
    # ------------------------------------------------------------

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

    def _get_recent_points(self, device_id: int, config: Dict[str, Union[int, float]]):
        """
        Get recent GPS points for validation purposes.

        Retrieves recent tracking points within a configurable time window
        for duplicate detection and validation operations.

        Args:
            device_id: GPS device ID to fetch points for
            config: Validation configuration dict containing duplicate_time_window

        Returns:
            odoo.models.Model: Recordset of gps.tracking.point records ordered by timestamp desc
            Limited to 15 records within the configured time window

        Raises:
            Exception: Database errors are logged and empty recordset returned
        """
        window_seconds = config.get("duplicate_time_window", 15)

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
                    limit=15,
                )
            )
            return recent_points

        except Exception as e:
            _logger.error(
                "Error fetching recent points for device %d: %s", device_id, e
            )
            return request.env["gps.tracking.point"].sudo().browse([])

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
            if "," not in latlng_str:
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

            # Convert from milliseconds to seconds and create datetime
            return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).replace(
                tzinfo=None
            )
        except (ValueError, OSError, TypeError) as e:
            return None

    def _process_odometer(self, value: Union[int, float]) -> Optional[float]:
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

    def _process_engine_temperature(self, value: Union[int, float]) -> Optional[float]:
        """
        Process engine temperature value (convert from decigrade to degree)

        Args:
            value: engine temperature value in decigrades

        Returns:
            Engine temperature value in degree or None if invalid
        """
        try:
            temperature_value = float(value) / 10.0
            return temperature_value
        except (ValueError, TypeError) as e:
            return None

    # ------------------------------------------------------------
    # VALIDATIONS
    # ------------------------------------------------------------

    def _validate_payload(
        self,
        payload: Dict[str, Any],
        processing_stats: Dict[str, Union[datetime, float, int]],
    ) -> Tuple[bool, str, Any, Dict[str, Any]]:
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
        device = ()
        recent_points = ()
        vals = {}

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
                "record_duplication",
                self.validate_record_duplication,
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
        ]

        for rule_name, validator_func, severity in validation_rules:
            try:
                if rule_name == "prerequisite_validation":
                    is_valid, message, device = validator_func(payload)
                else:
                    is_valid, message = validator_func(vals, config, recent_points)

                if is_valid:
                    processing_stats["quality_checks_passed"] += 1
                    if rule_name == "prerequisite_validation":
                        vals = self._prepare_tracking_point_vals(device.id, payload)
                        recent_points = self._get_recent_points(device.id, config)
                elif not is_valid:
                    processing_stats["quality_checks_failed"] += 1
                    if severity == "critical":
                        errors.append(f"{rule_name}: {message}")
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
                vals.get("imei", "unknown") if vals else payload.get("14", "unknown")
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

    def _validate_prerequisites(self, payload: Dict[str, Any]) -> Tuple[bool, str, Any]:
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

    def _validate_range(
        self,
        param_name: str,
        min_val: Union[int, float],
        max_val: Union[int, float],
        value: Union[int, float],
        unit: str = "",
    ):
        """
        Generic range validation helper to eliminate duplicate validation patterns.

        Args:
            param_name: Parameter name for error messages
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            value: Value to validate
            unit: Unit suffix for error messages

        Returns:
            Tuple of (is_valid, error_message)
        """
        if value is None or value == 0:
            return False, f"No {param_name} to validate"

        if not (min_val <= value <= max_val):
            return (
                False,
                f"Invalid {param_name}: {value}{unit} (range: {min_val}-{max_val}{unit})",
            )

        return True, f"{param_name} valid"

    def _validate_timestamp(
        self,
        vals: Dict[str, Any],
        config: Dict[str, Union[int, float]],
        recent_points: Optional[Any] = None,
    ) -> Tuple[bool, str]:
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
        max_future_minutes = config.get("max_time_future_minutes", 5)
        max_future_seconds = max_future_minutes * 60
        if time_diff > max_future_seconds:
            return (
                False,
                f"Timestamp too far in future: {time_diff/60:.1f} minutes ahead",
            )

        # Check for very old timestamps (more than configured max time gap)
        max_past_hours = config.get("max_time_past_hours", 24)
        max_past_seconds = max_past_hours * 3600
        if time_diff < -max_past_seconds:
            return (
                False,
                f"Timestamp too old: {abs(time_diff/3600):.1f} hours ago (maximum: {max_past_hours} hours)",
            )

        return True, "Timestamp quality valid"

    def _validate_coordinates(
        self,
        vals: Dict[str, Any],
        config: Dict[str, Union[int, float]],
        recent_points: Optional[Any] = None,
    ) -> Tuple[bool, str]:
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
            return (
                False,
                "No coordinates to validate",
            )
        if lat == 0.0 and lng == 0.0:
            return (
                False,
                "Invalid null coordinates (0.0, 0.0) - GPS signal not acquired",
            )

        # Use cached config and generic range validator
        is_valid, msg = self._validate_range(
            "latitude", config["min_latitude"], config["max_latitude"], lat
        )
        if not is_valid:
            return False, msg

        is_valid, msg = self._validate_range(
            "longitude", config["min_longitude"], config["max_longitude"], lng
        )
        if not is_valid:
            return False, msg

        return True, f"Coordinates valid: ({lat:.6f}, {lng:.6f})"

    def _validate_gps_accuracy(
        self,
        vals: Dict[str, Any],
        config: Dict[str, Union[int, float]],
        recent_points: Optional[Any] = None,
    ) -> Tuple[bool, str]:
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
        self,
        vals: Dict[str, Any],
        config: Dict[str, Union[int, float]],
        recent_points: Optional[Any] = None,
    ) -> Tuple[bool, str]:
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
            "fuel level", 0, config["max_fuel_level"], vals.get("fuel_level", 0), "%"
        )
        if (
            not is_valid and vals.get("fuel_level", 0) > 0
        ):  # Only validate if fuel level provided
            return False, msg

        is_valid, msg = self._validate_range(
            "engine hours",
            0,
            config["max_engine_hours"],
            vals.get("engine_total_hours", 0),
        )
        if not is_valid and vals.get("engine_total_hours", 0) > 0:
            return False, msg

        # Speed validation (basic range, not change rate)
        is_valid, msg = self._validate_range(
            "speed", 0, config["max_realistic_speed"], vals.get("speed", 0), " km/h"
        )
        if not is_valid and vals.get("speed", 0) > 0:
            return False, msg

        # Engine RPM validation
        engine_rpm = vals.get("engine_speed_rpm", 0)
        if engine_rpm and (engine_rpm < 0 or engine_rpm > 8000):
            return False, f"Invalid engine RPM: {engine_rpm} (range: 0-8000 RPM)"

        # Electrical parameter validations
        is_valid, msg = self._validate_range(
            "external voltage",
            config["min_external_voltage"],
            config["max_external_voltage"],
            vals.get("external_voltage", 0),
            "V",
        )
        if not is_valid and vals.get("external_voltage", 0) > 0:
            return False, msg

        is_valid, msg = self._validate_range(
            "battery voltage",
            config["min_internal_voltage"],
            config["max_internal_voltage"],
            vals.get("battery_voltage", 0),
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
            "GSM signal",
            config["min_gsm_signal"],
            config["max_gsm_signal"],
            vals.get("gsm_signal", 0),
        )
        if not is_valid and vals.get("gsm_signal", 0) > 0:
            return False, msg

        return True, "Comprehensive parameters valid"

    def _validate_speed_parameters(
        self,
        vals: Dict[str, Any],
        config: Dict[str, Union[int, float]],
        recent_points: Any,
    ) -> Tuple[bool, str]:
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

        return True, "Speed parameters valid"

    def validate_record_duplication(
        self,
        vals: Dict[str, Any],
        config: Dict[str, Union[int, float]],
        recent_points: Any,
    ) -> Tuple[bool, str]:
        """
        Optimized duplicate detection using cached config and recent points.

        Checks if incoming GPS point is a duplicate of recent points within
        a configurable time window and coordinate tolerance.

        Args:
            vals: Dictionary of processed GPS values containing timestamp, latitude, longitude
            config: Pre-loaded validation configuration with duplicate_time_window and coordinate_tolerance
            recent_points: Cached recent points recordset for comparison

        Returns:
            tuple[bool, str]: (is_valid, error_message)
                - True, "No duplicate found" if point is unique
                - False, "Duplicate point detected..." if duplicate found

        Raises:
            Exception: Caught and logged, returns (False, error_message) for safety

        Algorithm:
            Compares timestamp and coordinates within configured tolerances
            against recent points from the same device.
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
