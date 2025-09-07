"""Improved geometry conversion helper using Shapely.

This module provides a clean interface for converting between different
geometry representations using Shapely's robust parsers.
"""

import json
import logging

from typing import Any, Optional, TYPE_CHECKING

try:
    from odoo import _
except ImportError:
    # Fallback for testing without Odoo
    def _(text):
        return text


logger = logging.getLogger(__name__)

try:
    import geojson
    from shapely import wkb, wkt
    from shapely.geometry import Point, LineString, Polygon, shape, mapping
    from shapely.geometry.base import BaseGeometry

    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False
    logger.warning(_("Shapely or geojson are not available in the sys path"))
    # Provide dummy type for type hints when Shapely is not available
    if TYPE_CHECKING:
        from shapely.geometry.base import BaseGeometry
    else:
        BaseGeometry = object


def to_shapely(value: Any) -> Optional[BaseGeometry]:
    """Convert any geometry format to Shapely geometry object.

    Intelligently detects and converts various geometry formats including
    WKT, GeoJSON, WKB, coordinate arrays, and existing Shapely objects.

    Args:
        value: Geometry in any supported format:
            - str: GeoJSON string, WKT string, or WKB hex string
            - dict: GeoJSON dictionary
            - list/tuple: Coordinate array
            - BaseGeometry: Existing Shapely geometry

    Returns:
        BaseGeometry: Shapely geometry object, or None if value is empty.

    Raises:
        ValueError: If format cannot be determined or is invalid.
        ImportError: If Shapely is not available.
    """
    if not SHAPELY_AVAILABLE:
        raise ImportError(_("Shapely is required but not installed"))

    if not value:
        return None

    # Already a Shapely geometry
    if isinstance(value, BaseGeometry):
        return value

    # String input - could be GeoJSON, WKT, or WKB hex
    if isinstance(value, str):
        value = value.strip()

        # Remove SRID prefix if present (for WKT)
        srid = None
        if value.startswith("SRID="):
            parts = value.split(";", 1)
            if len(parts) == 2:
                srid = parts[0].replace("SRID=", "")
                value = parts[1]

        # GeoJSON string (contains braces)
        if "{" in value and "}" in value:
            try:
                geo_dict = json.loads(value)
                return shape(geo_dict)
            except (json.JSONDecodeError, Exception) as e:
                # Not valid JSON, might be WKT with complex structure
                pass

        # Try WKB hex (all hex characters)
        try:
            # Check if it's a valid hex string
            int(value[:10], 16)  # Test first 10 chars
            if len(value) % 2 == 0:  # WKB hex must have even length
                return wkb.loads(value, hex=True)
        except (ValueError, Exception):
            pass

        # Must be WKT
        try:
            return wkt.loads(value)
        except Exception as e:
            raise ValueError(_("Invalid WKT string: %s") % str(e))

    # GeoJSON dictionary
    if isinstance(value, dict):
        if "type" in value and "coordinates" in value:
            return shape(value)
        raise ValueError(
            _("Invalid GeoJSON dictionary: missing 'type' or 'coordinates'")
        )

    # Coordinate array/tuple
    if isinstance(value, (list, tuple)):
        if not value:
            raise ValueError(_("Empty coordinate array"))

        # Single point: [x, y] or (x, y)
        if len(value) == 2 and isinstance(value[0], (int, float)):
            return Point(value)

        # Multiple points
        if all(isinstance(c, (list, tuple)) and len(c) >= 2 for c in value):
            # Check if it's a closed ring (polygon)
            if len(value) > 3 and value[0] == value[-1]:
                return Polygon(value)
            else:
                return LineString(value)

        raise ValueError(_("Invalid coordinate array format"))

    # Try to use object's WKT representation if available
    if hasattr(value, "wkt"):
        return wkt.loads(value.wkt)

    raise ValueError(
        _(
            "Unsupported geometry format: %s. Expected WKT, GeoJSON, "
            "coordinate array, or Shapely geometry"
        )
        % type(value).__name__
    )


def to_wkt(value: Any, srid: Optional[int] = None) -> Optional[str]:
    """Convert any geometry format to WKT string.

    Args:
        value: Geometry in any supported format.
        srid: Optional SRID to include in output.

    Returns:
        str: WKT representation with optional SRID prefix, or None if empty.
    """
    geom = to_shapely(value)
    if not geom:
        return None

    wkt_str = geom.wkt
    if srid:
        return f"SRID={srid};{wkt_str}"
    return wkt_str


def to_geojson(value: Any) -> Optional[dict]:
    """Convert any geometry format to GeoJSON dictionary.

    Args:
        value: Geometry in any supported format.

    Returns:
        dict: GeoJSON representation, or None if empty.
    """
    geom = to_shapely(value)
    if not geom:
        return None

    # Use Shapely's mapping function for GeoJSON conversion
    return mapping(geom)


def to_geojson_string(value: Any) -> Optional[str]:
    """Convert any geometry format to GeoJSON string.

    Args:
        value: Geometry in any supported format.

    Returns:
        str: GeoJSON string representation, or None if empty.
    """
    geojson_dict = to_geojson(value)
    if not geojson_dict:
        return None

    return json.dumps(geojson_dict)


def to_sql_param(value: Any, srid: int = 3857) -> Optional[str]:
    """Convert geometry to PostGIS-ready SQL parameter.

    Args:
        value: Geometry in any supported format.
        srid: Target SRID for the geometry (default: 3857).

    Returns:
        str: SQL-safe geometry string for PostGIS (SRID=xxxx;WKT format).
    """
    return to_wkt(value, srid)


def validate_geometry(value: Any, expected_type: Optional[str] = None) -> bool:
    """Validate that geometry is valid and optionally of expected type.

    Args:
        value: Geometry to validate.
        expected_type: Optional expected geometry type (e.g., 'POINT').

    Returns:
        bool: True if valid, False otherwise.
    """
    try:
        geom = to_shapely(value)
        if not geom:
            return False

        if not geom.is_valid:
            return False

        if expected_type:
            return geom.geom_type.upper() == expected_type.upper()

        return True
    except Exception:
        return False


def get_geometry_type(value: Any) -> Optional[str]:
    """Get the type of a geometry.

    Args:
        value: Input geometry.

    Returns:
        str: Geometry type (e.g., 'Point', 'Polygon') or None if invalid.
    """
    try:
        geom = to_shapely(value)
        return geom.geom_type if geom else None
    except Exception:
        return None


def get_srid_from_wkt(value: str) -> Optional[int]:
    """Extract SRID from WKT string if present.

    Args:
        value: WKT string possibly prefixed with SRID.

    Returns:
        int: SRID value or None if not present.
    """
    if isinstance(value, str) and value.startswith("SRID="):
        try:
            srid_part = value.split(";")[0].replace("SRID=", "")
            return int(srid_part)
        except (ValueError, IndexError):
            pass
    return None
