from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """Inherit ResConfigSettings"""

    _inherit = "res.config.settings"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    inactivity_threshold_hours = fields.Float(
        default=2,
        config_parameter="gps_tracking.inactivity_threshold_hours",
    )
    inactivity_warning = fields.Boolean(
        default=True,
        config_parameter="gps_tracking.inactivity_warning_enabled",
    )
    inactivity_warning_hours = fields.Float(
        default=1.5,
        config_parameter="gps_tracking.inactivity_warning_hours",
    )
    # ========================================
    # GPS ACCURACY PARAMETERS
    # ========================================

    min_satellites = fields.Integer(
        string="Minimum Satellites",
        default=4,
        help="Minimum number of satellites required for accurate GPS positioning",
        config_parameter="gps_tracking.validation.min_satellites",
    )
    max_hdop = fields.Float(
        string="Maximum HDOP",
        default=5.0,
        help="Maximum Horizontal Dilution of Precision allowed (lower is better)",
        config_parameter="gps_tracking.validation.max_hdop",
    )

    # ========================================
    # COORDINATE PARAMETERS
    # ========================================

    min_latitude = fields.Float(
        string="Minimum Latitude",
        default=-90.0,
        help="Minimum allowed latitude value (degrees)",
        config_parameter="gps_tracking.validation.min_latitude",
    )
    max_latitude = fields.Float(
        string="Maximum Latitude",
        default=90.0,
        help="Maximum allowed latitude value (degrees)",
        config_parameter="gps_tracking.validation.max_latitude",
    )
    min_longitude = fields.Float(
        string="Minimum Longitude",
        default=-180.0,
        help="Minimum allowed longitude value (degrees)",
        config_parameter="gps_tracking.validation.min_longitude",
    )
    max_longitude = fields.Float(
        string="Maximum Longitude",
        default=180.0,
        help="Maximum allowed longitude value (degrees)",
        config_parameter="gps_tracking.validation.max_longitude",
    )

    # ========================================
    # VEHICLE PARAMETERS
    # ========================================

    max_realistic_speed = fields.Float(
        string="Maximum Realistic Speed (km/h)",
        default=300.0,
        help="Maximum reasonable speed for ground vehicles",
        config_parameter="gps_tracking.validation.max_realistic_speed",
    )
    max_fuel_level = fields.Float(
        string="Maximum Fuel Level (%)",
        default=100.0,
        help="Maximum fuel level percentage allowed",
        config_parameter="gps_tracking.validation.max_fuel_level",
    )
    max_engine_hours = fields.Integer(
        string="Maximum Engine Hours",
        default=50000,
        help="Maximum reasonable engine hours for validation",
        config_parameter="gps_tracking.validation.max_engine_hours",
    )

    # ========================================
    # ELECTRICAL PARAMETERS
    # ========================================

    min_external_voltage = fields.Float(
        string="Minimum External Voltage (V)",
        default=8.0,
        help="Minimum expected external/vehicle voltage",
        config_parameter="gps_tracking.validation.min_external_voltage",
    )
    max_external_voltage = fields.Float(
        string="Maximum External Voltage (V)",
        default=30.0,
        help="Maximum expected external/vehicle voltage",
        config_parameter="gps_tracking.validation.max_external_voltage",
    )
    min_internal_voltage = fields.Float(
        string="Minimum Internal Battery Voltage (V)",
        default=2.5,
        help="Minimum expected internal battery voltage",
        config_parameter="gps_tracking.validation.min_internal_voltage",
    )
    max_internal_voltage = fields.Float(
        string="Maximum Internal Battery Voltage (V)",
        default=5.5,
        help="Maximum expected internal battery voltage",
        config_parameter="gps_tracking.validation.max_internal_voltage",
    )
    min_gsm_signal = fields.Integer(
        string="Minimum GSM Signal",
        default=0,
        help="Minimum GSM signal strength (0-31 scale)",
        config_parameter="gps_tracking.validation.min_gsm_signal",
    )
    max_gsm_signal = fields.Integer(
        string="Maximum GSM Signal",
        default=31,
        help="Maximum GSM signal strength (0-31 scale)",
        config_parameter="gps_tracking.validation.max_gsm_signal",
    )

    # ========================================
    # SPEED CHANGE PARAMETERS
    # ========================================

    max_speed_change_kmh_per_sec = fields.Float(
        string="Max Speed Change (km/h per second)",
        default=10.0,
        help="Maximum allowed speed change per second to detect unrealistic changes",
        config_parameter="gps_tracking.validation.max_speed_change_kmh_per_sec",
    )
    speed_validation_window_seconds = fields.Integer(
        string="Speed Validation Window (seconds)",
        default=30,
        help="Time window for speed change validation",
        config_parameter="gps_tracking.validation.speed_validation_window_seconds",
    )

    # ========================================
    # TEMPORAL PARAMETERS
    # ========================================

    max_time_gap_hours = fields.Float(
        string="Maximum Time Gap (hours)",
        default=24.0,
        help="Maximum allowed time gap between current time and GPS timestamp",
        config_parameter="gps_tracking.validation.max_time_gap_hours",
    )
    min_time_interval_seconds = fields.Integer(
        string="Minimum Time Interval (seconds)",
        default=1,
        help="Minimum time interval between consecutive GPS points",
        config_parameter="gps_tracking.validation.min_time_interval_seconds",
    )

    # ========================================
    # DUPLICATE DETECTION PARAMETERS
    # ========================================

    duplicate_time_window_seconds = fields.Integer(
        string="Duplicate Time Window (seconds)",
        default=10,
        help="Time window for duplicate point detection",
        config_parameter="gps_tracking.validation.duplicate_time_window_seconds",
    )
    duplicate_coordinate_tolerance = fields.Float(
        string="Duplicate Coordinate Tolerance",
        default=0.00001,
        help="Coordinate tolerance for duplicate detection (degrees)",
        config_parameter="gps_tracking.validation.duplicate_coordinate_tolerance",
    )
    duplicate_extended_window_seconds = fields.Integer(
        string="Extended Duplicate Window (seconds)",
        default=300,
        help="Extended time window for comprehensive duplicate checking",
        config_parameter="gps_tracking.validation.duplicate_extended_window_seconds",
    )

    # ========================================
    # VALIDATION BEHAVIOR
    # ========================================

    enable_validation_warnings = fields.Boolean(
        string="Enable Validation Warnings",
        default=True,
        help="Enable non-critical validation warnings in logs",
        config_parameter="gps_tracking.validation.enable_warnings",
    )
    strict_validation_mode = fields.Boolean(
        string="Strict Validation Mode",
        default=False,
        help="Enable strict validation mode - treat warnings as errors",
        config_parameter="gps_tracking.validation.strict_mode",
    )
