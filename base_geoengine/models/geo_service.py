import logging
import time

from collections import OrderedDict

from odoo import _, api, models

logger = logging.getLogger(__name__)


class GeoService(models.TransientModel):
    """Service for managing spatial operation caches and performance monitoring.

    Provides caching functionality for spatial operations, coordinate transformations,
    and search results to improve performance of geospatial queries.
    """

    _name = "geo.service"
    _description = "GeoEngine Service"

    def __init__(self, env, ids, prefetch_ids):
        """Initialize the geo service with cache storage."""
        super().__init__(env, ids, prefetch_ids)
        self._init_caches()

    def _init_caches(self):
        """Initialize cache dictionaries if they don't exist."""
        if not hasattr(self.__class__, "_transform_cache"):
            self.__class__._transform_cache = OrderedDict()
            self.__class__._operation_cache = OrderedDict()
            self.__class__._search_cache = OrderedDict()
            self.__class__._cache_stats = {
                "hits": 0,
                "misses": 0,
                "last_clear": time.time(),
            }

    @api.model
    def _get_cache_config(self):
        """Get cache configuration parameters.

        Returns:
            dict: Cache configuration with timeout and max entries.
        """
        config_obj = self.env["ir.config_parameter"].sudo()
        return {
            "enabled": config_obj.get_param("base_geoengine.enable_cache", "True")
            == "True",
            "timeout": int(
                config_obj.get_param("base_geoengine.cache_timeout", "3600")
            ),
            "max_entries": int(
                config_obj.get_param("base_geoengine.max_cache_entries", "1000")
            ),
            "monitor_performance": config_obj.get_param(
                "base_geoengine.monitor_cache", "True"
            )
            == "True",
        }

    @api.model
    def _cleanup_expired_cache(self, cache_dict, timeout):
        """Remove expired entries from cache.

        Args:
            cache_dict (OrderedDict): Cache dictionary to clean.
            timeout (int): Timeout in seconds.
        """
        current_time = time.time()
        expired_keys = [
            key
            for key, (timestamp, _) in cache_dict.items()
            if current_time - timestamp > timeout
        ]
        for key in expired_keys:
            del cache_dict[key]

    @api.model
    def _enforce_cache_size(self, cache_dict, max_entries):
        """Enforce maximum cache size using LRU eviction.

        Args:
            cache_dict (OrderedDict): Cache dictionary to limit.
            max_entries (int): Maximum number of entries.
        """
        while len(cache_dict) > max_entries:
            cache_dict.popitem(last=False)  # Remove oldest item

    @api.model
    def get_cached_transform(self, source_srid, target_srid, geometry_wkt):
        """Get cached coordinate transformation result.

        Args:
            source_srid (int): Source spatial reference system ID.
            target_srid (int): Target spatial reference system ID.
            geometry_wkt (str): Geometry in WKT format.

        Returns:
            str or None: Cached transformed geometry WKT or None if not cached.
        """
        cache_config = self._get_cache_config()
        if not cache_config["enabled"]:
            return None

        cache_key = f"{source_srid}_{target_srid}_{hash(geometry_wkt)}"

        # Clean expired entries
        self._cleanup_expired_cache(self._transform_cache, cache_config["timeout"])

        if cache_key in self._transform_cache:
            timestamp, result = self._transform_cache[cache_key]
            # Move to end (LRU)
            self._transform_cache.move_to_end(cache_key)
            self._cache_stats["hits"] += 1
            return result

        self._cache_stats["misses"] += 1
        return None

    @api.model
    def set_cached_transform(self, source_srid, target_srid, geometry_wkt, result):
        """Cache coordinate transformation result.

        Args:
            source_srid (int): Source spatial reference system ID.
            target_srid (int): Target spatial reference system ID.
            geometry_wkt (str): Original geometry in WKT format.
            result (str): Transformed geometry WKT.
        """
        cache_config = self._get_cache_config()
        if not cache_config["enabled"]:
            return

        cache_key = f"{source_srid}_{target_srid}_{hash(geometry_wkt)}"
        self._transform_cache[cache_key] = (time.time(), result)

        # Enforce size limit
        self._enforce_cache_size(self._transform_cache, cache_config["max_entries"])

    @api.model
    def get_cached_operation(self, operation, geometry1_wkt, geometry2_wkt=None):
        """Get cached spatial operation result.

        Args:
            operation (str): Spatial operation name (intersects, contains, etc.).
            geometry1_wkt (str): First geometry in WKT format.
            geometry2_wkt (str, optional): Second geometry in WKT format.

        Returns:
            Any or None: Cached operation result or None if not cached.
        """
        cache_config = self._get_cache_config()
        if not cache_config["enabled"]:
            return None

        cache_key = f"{operation}_{hash(geometry1_wkt)}_{hash(geometry2_wkt or '')}"

        # Clean expired entries
        self._cleanup_expired_cache(self._operation_cache, cache_config["timeout"])

        if cache_key in self._operation_cache:
            timestamp, result = self._operation_cache[cache_key]
            # Move to end (LRU)
            self._operation_cache.move_to_end(cache_key)
            self._cache_stats["hits"] += 1
            return result

        self._cache_stats["misses"] += 1
        return None

    @api.model
    def set_cached_operation(self, operation, geometry1_wkt, geometry2_wkt, result):
        """Cache spatial operation result.

        Args:
            operation (str): Spatial operation name.
            geometry1_wkt (str): First geometry in WKT format.
            geometry2_wkt (str): Second geometry in WKT format.
            result: Operation result to cache.
        """
        cache_config = self._get_cache_config()
        if not cache_config["enabled"]:
            return

        cache_key = f"{operation}_{hash(geometry1_wkt)}_{hash(geometry2_wkt or '')}"
        self._operation_cache[cache_key] = (time.time(), result)

        # Enforce size limit
        self._enforce_cache_size(self._operation_cache, cache_config["max_entries"])

    @api.model
    def clear_geo_cache(self):
        """Clear all spatial operation caches."""
        self._transform_cache.clear()
        self._operation_cache.clear()
        self._search_cache.clear()
        self._cache_stats = {"hits": 0, "misses": 0, "last_clear": time.time()}
        logger.info("Spatial caches cleared")

    @api.model
    def get_cache_stats(self):
        """Get cache performance statistics.

        Returns:
            dict: Dictionary containing cache statistics.
        """
        total_requests = self._cache_stats["hits"] + self._cache_stats["misses"]
        hit_ratio = (
            self._cache_stats["hits"] / total_requests if total_requests > 0 else 0
        )

        return {
            "transform_cache_size": len(self._transform_cache),
            "operation_cache_size": len(self._operation_cache),
            "search_cache_size": len(self._search_cache),
            "cache_hits": self._cache_stats["hits"],
            "cache_misses": self._cache_stats["misses"],
            "hit_ratio": hit_ratio,
            "last_clear": self._cache_stats["last_clear"],
        }

    @api.model
    def log_cache_performance(self):
        """Log cache performance statistics if monitoring is enabled."""
        cache_config = self._get_cache_config()
        if cache_config["monitor_performance"]:
            stats = self.get_cache_stats()
            logger.info(
                "GeoEngine Cache Stats - Transform: %d, Operations: %d, Hit Ratio: %.1f%%",
                stats["transform_cache_size"],
                stats["operation_cache_size"],
                stats["hit_ratio"] * 100,
            )
