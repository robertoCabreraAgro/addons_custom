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

            # Get device IMEI
            # TODO - Support alternative identifiers for example not Teltonika devices
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

            # 1. Basic GPS quality validation (including speed validation)
            is_quality_valid, quality_error = self._validate_gps_quality(
                vals, device.id
            )
            if not is_quality_valid:
                processing_stats["quality_checks_failed"] += 1
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

            # === CREATE TRACKING POINT WITH TRANSACTION MANAGEMENT ===

            db_start_time = datetime.now()
            
            # Use savepoint for atomic database operations
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
                    
            except Exception as db_error:
                # Transaction automatically rolled back due to savepoint context
                processing_stats["db_operation_time"] = (
                    datetime.now() - db_start_time
                ).total_seconds()
                
                error_msg = f"Database transaction failed: {str(db_error)}"
                self._log_webhook_failure(
                    start_time, remote_addr, imei, error_msg, processing_stats
                )
                return self.RESPONSE_FAILURE

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
        is_valid, error = self._validate_speed_parameters(device_id, vals)
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
        Validate GPS signal accuracy based on satellite count and HDOP.

        Args:
            vals: Dictionary of processed GPS values

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Get validation parameters from system config
        param_obj = request.env["ir.config_parameter"].sudo()
        min_satellites = int(param_obj.get_param(
            "gps_tracking.validation.min_satellites", 
            default=self.MIN_SATELLITES_FOR_ACCURACY
        ))
        max_hdop = float(param_obj.get_param(
            "gps_tracking.validation.max_hdop",
            default=5.0
        ))
        
        # Check GPS accuracy based on satellite count
        satellites = vals.get("satellites", 0)
        if satellites and satellites < min_satellites:
            return (
                False,
                f"Low GPS accuracy: only {satellites} satellites (minimum: {min_satellites})",
            )

        # Check HDOP if available
        hdop = vals.get("gnss_hdop", 0)
        if hdop and hdop > max_hdop:
            return (
                False,
                f"Poor GPS precision: HDOP {hdop} exceeds maximum {max_hdop}",
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

        # Get validation parameters from system config
        param_obj = request.env["ir.config_parameter"].sudo()
        min_lat = float(param_obj.get_param(
            "gps_tracking.validation.min_latitude",
            default=self.MIN_LATITUDE
        ))
        max_lat = float(param_obj.get_param(
            "gps_tracking.validation.max_latitude",
            default=self.MAX_LATITUDE
        ))
        min_lng = float(param_obj.get_param(
            "gps_tracking.validation.min_longitude", 
            default=self.MIN_LONGITUDE
        ))
        max_lng = float(param_obj.get_param(
            "gps_tracking.validation.max_longitude",
            default=self.MAX_LONGITUDE
        ))
        zero_tolerance = float(param_obj.get_param(
            "gps_tracking.validation.zero_coordinate_tolerance",
            default=0.001
        ))

        # Check coordinate bounds
        if not (min_lat <= lat <= max_lat):
            return (
                False,
                f"Invalid latitude {lat}: must be between {min_lat} and {max_lat}",
            )

        if not (min_lng <= lng <= max_lng):
            return (
                False,
                f"Invalid longitude {lng}: must be between {min_lng} and {max_lng}",
            )

        # Check for suspicious zero coordinates (likely invalid data)
        if abs(lat) < zero_tolerance and abs(lng) < zero_tolerance:
            return (
                False,
                f"Suspicious zero coordinates: lat={lat}, lng={lng}",
            )

        lat_str = str(lat)
        lng_str = str(lng)

        # Check if coordinates have sufficient precision
        lat_precision = len(lat_str.split(".")[-1]) if "." in lat_str else 0
        lng_precision = len(lng_str.split(".")[-1]) if "." in lng_str else 0

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

        return True, "Coordinate quality valid"

    def _validate_vehicle_parameters(self, vals: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate vehicle-specific parameters like speed, fuel level and engine hours.

        Args:
            vals: Dictionary of processed GPS values

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Get validation parameters from system config
        param_obj = request.env["ir.config_parameter"].sudo()
        max_fuel_level = float(param_obj.get_param(
            "gps_tracking.validation.max_fuel_level",
            default=100.0
        ))
        max_engine_hours = int(param_obj.get_param(
            "gps_tracking.validation.max_engine_hours",
            default=50000
        ))
        min_external_voltage = float(param_obj.get_param(
            "gps_tracking.validation.min_external_voltage",
            default=8.0
        ))
        max_external_voltage = float(param_obj.get_param(
            "gps_tracking.validation.max_external_voltage",
            default=30.0
        ))

        # Validate fuel level
        fuel_level = vals.get("fuel_level", 0)
        if fuel_level and (fuel_level < 0 or fuel_level > max_fuel_level):
            return False, f"Invalid fuel level: {fuel_level}% (range: 0-{max_fuel_level}%)"

        # Validate engine hours
        engine_hours = vals.get("engine_total_hours", 0)
        if engine_hours and engine_hours > max_engine_hours:
            return (
                False,
                f"Invalid engine hours: {engine_hours} (maximum: {max_engine_hours})",
            )

        # Validate engine RPM
        engine_rpm = vals.get("engine_speed_rpm", 0)
        if engine_rpm and (engine_rpm < 0 or engine_rpm > 8000):
            return False, f"Invalid engine RPM: {engine_rpm} (range: 0-8000 RPM)"

        # Validate external voltage (vehicle battery)
        external_voltage = vals.get("external_voltage", 0)
        if external_voltage and (external_voltage < min_external_voltage or external_voltage > max_external_voltage):
            return (
                False,
                f"Invalid external voltage: {external_voltage}V (range: {min_external_voltage}-{max_external_voltage}V)",
            )

        return True, "Vehicle parameters valid"

    def _validate_electrical_parameters(self, vals: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate electrical system parameters like voltage.

        Args:
            vals: Dictionary of processed GPS values

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Get validation parameters from system config
        param_obj = request.env["ir.config_parameter"].sudo()
        min_internal_voltage = float(param_obj.get_param(
            "gps_tracking.validation.min_internal_voltage",
            default=2.5
        ))
        max_internal_voltage = float(param_obj.get_param(
            "gps_tracking.validation.max_internal_voltage",
            default=5.5
        ))

        # Validate internal battery voltage (device battery)
        battery_voltage = vals.get("battery_voltage", 0)
        if battery_voltage and (battery_voltage < min_internal_voltage or battery_voltage > max_internal_voltage):
            return (
                False,
                f"Invalid battery voltage: {battery_voltage}V (range: {min_internal_voltage}-{max_internal_voltage}V)",
            )

        # Validate battery current
        battery_current = vals.get("battery_current", 0)
        if battery_current and abs(battery_current) > 5000:  # 5A in mA
            return (
                False,
                f"Invalid battery current: {battery_current}mA (typical range: -5000 to 5000mA)",
            )

        return True, "Electrical parameters valid"

    def _validate_network_parameters(self, vals: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate network system parameters like GSM signal readings.

        Args:
            vals: Dictionary of processed GPS values

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Get validation parameters from system config
        param_obj = request.env["ir.config_parameter"].sudo()
        min_gsm_signal = int(param_obj.get_param(
            "gps_tracking.validation.min_gsm_signal",
            default=0
        ))
        max_gsm_signal = int(param_obj.get_param(
            "gps_tracking.validation.max_gsm_signal",
            default=31
        ))

        # Validate GSM signal strength
        gsm_signal = vals.get("gsm_signal", 0)
        if gsm_signal and (gsm_signal < min_gsm_signal or gsm_signal > max_gsm_signal):
            return (
                False,
                f"Invalid battery voltage: {battery_voltage}V (typical range: 3-5V)",
            )

        return True, "Network parameters valid"

    def _validate_speed_parameters(
        self, device_id: int = None, vals: Dict[str, Any]
    ) -> tuple[bool, str]:
        """
        Validate speed-related parameters including absolute speed and speed changes.

        Args:
            device_id: GPS device ID for temporal speed change validation (optional)
            vals: Dictionary of processed GPS values

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Get validation parameters from system config
        param_obj = request.env["ir.config_parameter"].sudo()
        max_realistic_speed = float(param_obj.get_param(
            "gps_tracking.validation.max_realistic_speed",
            default=self.MAX_REASONABLE_SPEED
        ))
        max_speed_change = float(param_obj.get_param(
            "gps_tracking.validation.max_speed_change_kmh_per_sec",
            default=10.0
        ))
        speed_window_seconds = int(param_obj.get_param(
            "gps_tracking.validation.speed_validation_window_seconds",
            default=30
        ))

        # Validate speed (basic range check)
        speed = vals.get("speed", 0)
        if speed and speed > max_realistic_speed:
            return (
                False,
                f"Unrealistic speed: {speed} km/h (maximum: {max_realistic_speed} km/h)",
            )

        if speed < 0:
            return (
                False,
                f"Invalid negative speed: {speed} km/h",
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

                    # Only validate if within the validation window
                    if 0 < abs(time_diff) <= speed_window_seconds:
                        speed_change = abs(speed - last_point.speed)
                        speed_change_per_second = speed_change / abs(time_diff)

                        if speed_change_per_second > max_speed_change:
                            return (
                                False,
                                f"Unrealistic speed change: {speed_change:.1f} km/h in {abs(time_diff):.1f} seconds",
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
        # Get validation parameters from system config
        param_obj = request.env["ir.config_parameter"].sudo()
        max_time_gap_hours = float(param_obj.get_param(
            "gps_tracking.validation.max_time_gap_hours",
            default=24.0
        ))
        min_time_interval_seconds = int(param_obj.get_param(
            "gps_tracking.validation.min_time_interval_seconds",
            default=1
        ))

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
            if abs(time_diff) < min_time_interval_seconds:
                return (
                    False,
                    f"Duplicate or too-frequent timestamp: {abs(time_diff):.1f}s interval (minimum: {min_time_interval_seconds}s)",
                )

            # Check for points too far in the future
            now = datetime.now()
            future_diff = (new_timestamp - now).total_seconds()
            if future_diff > 300:  # More than 5 minutes in the future
                return (
                    False,
                    f"Timestamp too far in future: {future_diff/60:.1f} minutes",
                )

            # Check for points too far in the past
            max_gap_seconds = max_time_gap_hours * 3600
            if time_diff < -max_gap_seconds:
                return (
                    False,
                    f"Timestamp too far in past: {abs(time_diff/3600):.1f} hours ago (maximum: {max_time_gap_hours} hours)",
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
        Enhanced duplicate detection with performance optimizations.

        Args:
            device_id: GPS device ID
            timestamp: Point timestamp
            latitude: GPS latitude (optional)
            longitude: GPS longitude (optional)

        Returns:
            True if duplicate detected
        """
        # Get validation parameters from system config
        param_obj = request.env["ir.config_parameter"].sudo()
        duplicate_time_window = int(param_obj.get_param(
            "gps_tracking.validation.duplicate_time_window_seconds",
            default=10
        ))
        coordinate_tolerance = float(param_obj.get_param(
            "gps_tracking.validation.duplicate_coordinate_tolerance",
            default=0.00001
        ))
        extended_window = int(param_obj.get_param(
            "gps_tracking.validation.duplicate_extended_window_seconds",
            default=300
        ))

        try:
            # Optimize: Check only recent points for better performance
            # Most duplicates occur within seconds, not the full window
            time_window_start = timestamp - timedelta(seconds=duplicate_time_window)
            time_window_end = timestamp + timedelta(seconds=duplicate_time_window)

            # Use more efficient query with proper indexing
            domain = [
                ("device_id", "=", device_id),
                ("timestamp", ">=", time_window_start),
                ("timestamp", "<=", time_window_end),
            ]

            # Performance optimization: Use count instead of search when coordinates not needed
            if latitude is None or longitude is None:
                # Simple timestamp-based duplicate check (faster)
                duplicate_count = request.env["gps.tracking.point"].sudo().search_count(domain)
                return duplicate_count > 0
            
            # Enhanced spatial duplicate detection using configurable tolerance
            # Use SQL query for better performance with spatial checks
            query = """
                SELECT id FROM gps_tracking_point 
                WHERE device_id = %s 
                AND timestamp >= %s 
                AND timestamp <= %s
                AND ABS(latitude - %s) <= %s
                AND ABS(longitude - %s) <= %s
                LIMIT 1
            """
            
            request.env.cr.execute(query, (
                device_id, time_window_start, time_window_end,
                latitude, coordinate_tolerance, longitude, coordinate_tolerance
            ))
            
            result = request.env.cr.fetchone()
            if result:
                return True
            
            # If no duplicates found in recent window, check extended window if needed
            if duplicate_time_window < extended_window:
                extended_start = timestamp - timedelta(seconds=extended_window)
                extended_end = timestamp + timedelta(seconds=extended_window)
                
                # Check extended window (less likely to find duplicates here)
                extended_query = """
                    SELECT id FROM gps_tracking_point 
                    WHERE device_id = %s 
                    AND timestamp >= %s 
                    AND timestamp < %s
                    AND ABS(latitude - %s) <= %s
                    AND ABS(longitude - %s) <= %s
                    LIMIT 1
                """
                
                request.env.cr.execute(extended_query, (
                    device_id, extended_start, time_window_start,
                    latitude, coordinate_tolerance, longitude, coordinate_tolerance
                ))
                
                extended_result = request.env.cr.fetchone()
                if extended_result:
                    return True

            return False

        except Exception as e:
            _logger.warning("Error in duplicate detection: %s", e)
            return False  # Don't block on validation errors
