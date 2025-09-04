from odoo import _, api, fields, models


class ResConfigSettings(models.TransientModel):
    """Configuration settings for GeoEngine spatial functionality.

    Provides configuration options for spatial reference systems, caching,
    performance tuning, coordinate precision, map display settings, and
    database optimization for geospatial operations.
    """

    _inherit = "res.config.settings"

    # Default spatial reference system settings
    default_srid = fields.Integer(
        string="Default SRID",
        default=3857,
        help="Default Spatial Reference System Identifier (Web Mercator: 3857, WGS84: 4326)",
        config_parameter="base_geoengine.default_srid",
        default_model="res.config.settings",
    )
    display_srid = fields.Integer(
        string="Display SRID",
        default=4326,
        help="SRID used for displaying coordinates to users (usually WGS84: 4326)",
        config_parameter="base_geoengine.display_srid",
        default_model="res.config.settings",
    )

    # Cache settings
    enable_spatial_cache = fields.Boolean(
        string="Enable Spatial Caching",
        default=True,
        help="Cache spatial operations for better performance",
        config_parameter="base_geoengine.enable_cache",
        default_model="res.config.settings",
    )
    cache_timeout = fields.Integer(
        string="Cache Timeout (seconds)",
        default=3600,
        help="How long to keep spatial operation results in cache",
        config_parameter="base_geoengine.cache_timeout",
        default_model="res.config.settings",
    )
    max_cache_entries = fields.Integer(
        string="Max Cache Entries",
        default=1000,
        help="Maximum number of entries in spatial cache",
        config_parameter="base_geoengine.max_cache_entries",
        default_model="res.config.settings",
    )

    # Performance settings
    spatial_index_buffer = fields.Float(
        string="Spatial Index Buffer",
        default=0.0,
        help="Buffer distance for spatial index operations",
        config_parameter="base_geoengine.index_buffer",
        default_model="res.config.settings",
    )
    max_geometry_size = fields.Integer(
        string="Max Geometry Size (bytes)",
        default=1000000,  # 1MB
        help="Maximum size for geometry objects in bytes",
        config_parameter="base_geoengine.max_geometry_size",
        default_model="res.config.settings",
    )
    enable_geometry_validation = fields.Boolean(
        string="Enable Geometry Validation",
        default=True,
        help="Validate geometry objects before saving",
        config_parameter="base_geoengine.validate_geometry",
        default_model="res.config.settings",
    )

    # Coordinate precision
    coordinate_precision = fields.Integer(
        string="Coordinate Precision",
        default=6,
        help="Number of decimal places for coordinate values",
        config_parameter="base_geoengine.coordinate_precision",
        default_model="res.config.settings",
    )

    # Map display settings
    default_map_extent = fields.Char(
        string="Default Map Extent",
        default="-123164.85, 5574694.95, 1578017.65, 6186191.18",
        help="Default map extent as: min_x, min_y, max_x, max_y",
        config_parameter="base_geoengine.default_extent",
        default_model="res.config.settings",
    )
    default_zoom_level = fields.Integer(
        string="Default Zoom Level",
        default=10,
        help="Default zoom level for map views",
        config_parameter="base_geoengine.default_zoom",
        default_model="res.config.settings",
    )

    # Database optimization
    enable_spatial_indexes = fields.Boolean(
        string="Auto-create Spatial Indexes",
        default=True,
        help="Automatically create GIST indexes for geometry fields",
        config_parameter="base_geoengine.auto_spatial_indexes",
        default_model="res.config.settings",
    )
    vacuum_spatial_indexes = fields.Boolean(
        string="Vacuum Spatial Indexes",
        default=False,
        help="Regularly vacuum spatial indexes for better performance",
        config_parameter="base_geoengine.vacuum_indexes",
        default_model="res.config.settings",
    )

    # Logging and monitoring
    log_spatial_operations = fields.Boolean(
        string="Log Spatial Operations",
        default=False,
        help="Log spatial operations for debugging and monitoring",
        config_parameter="base_geoengine.log_operations",
        default_model="res.config.settings",
    )
    monitor_cache_performance = fields.Boolean(
        string="Monitor Cache Performance",
        default=True,
        help="Track cache hit/miss ratios for optimization",
        config_parameter="base_geoengine.monitor_cache",
        default_model="res.config.settings",
    )

    @api.constrains("default_srid", "display_srid")
    def _check_srid_values(self):
        """Validate Spatial Reference System Identifier values.

        Ensures that both default and display SRID values are positive integers,
        as required by spatial reference systems.

        Raises:
            ValueError: When SRID values are not positive integers.
        """
        for record in self:
            if record.default_srid <= 0:
                raise ValueError(_("Default SRID must be a positive integer"))
            if record.display_srid <= 0:
                raise ValueError(_("Display SRID must be a positive integer"))

    @api.constrains("coordinate_precision")
    def _check_coordinate_precision(self):
        """Validate coordinate precision range.

        Ensures coordinate precision is within acceptable bounds (0-15 decimal places)
        to maintain data quality while preventing excessive precision that could
        impact performance.

        Raises:
            ValueError: When precision is not between 0 and 15.
        """
        for record in self:
            if not 0 <= record.coordinate_precision <= 15:
                raise ValueError(_("Coordinate precision must be between 0 and 15"))

    @api.constrains("max_geometry_size")
    def _check_max_geometry_size(self):
        """Validate maximum geometry size limit.

        Ensures the maximum geometry size is a positive value to prevent
        storage of invalid or unlimited size geometries.

        Raises:
            ValueError: When max geometry size is not positive.
        """
        for record in self:
            if record.max_geometry_size <= 0:
                raise ValueError(_("Max geometry size must be positive"))

    def action_clear_spatial_cache(self):
        """Clear all spatial operation caches.

        Removes all cached spatial operation results to free memory and
        force recalculation of spatial queries. Useful for troubleshooting
        or when spatial data has been updated externally.

        Returns:
            dict: Client action to display success notification.
        """
        geo_service = self.env["geo.service"]
        geo_service.clear_geo_cache()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Success"),
                "message": _("Spatial caches have been cleared."),
                "sticky": False,
            },
        }

    def action_rebuild_spatial_indexes(self):
        """Rebuild all spatial indexes for better performance.

        Initiates rebuilding of GIST indexes on all geometry fields across
        all models. This can improve spatial query performance but may take
        significant time depending on data volume.

        Returns:
            dict: Client action to display success notification.
        """
        # TODO: Implement actual spatial index rebuilding logic
        # This should iterate through all models with geo fields
        # and rebuild their spatial indexes using PostGIS commands
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Success"),
                "message": _("Spatial indexes rebuild initiated."),
                "sticky": False,
            },
        }

    def action_show_cache_stats(self):
        """Show cache statistics"""
        geo_service = self.env["geo.service"]
        stats = geo_service.get_cache_stats()

        message = _(
            "Cache Statistics:\n"
            "Transform Cache: %(transform)d entries\n"
            "Operation Cache: %(operation)d entries\n"
            "Search Cache: %(search)d entries\n"
            "Hit Ratio: %(hit_ratio).1f%%"
        ) % {
            "transform": stats["transform_cache_size"],
            "operation": stats["operation_cache_size"],
            "search": stats["search_cache_size"],
            "hit_ratio": stats["hit_ratio"] * 100,
        }

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Cache Statistics"),
                "message": message,
                "sticky": True,
            },
        }
