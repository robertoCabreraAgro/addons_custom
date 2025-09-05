import json
import logging

from operator import attrgetter

from odoo import _, fields
from odoo.tools import sql

from . import geo_convertion_helper as convert
from .geo_db import create_geo_column, create_geo_index

logger = logging.getLogger(__name__)

try:
    import geojson
    from shapely.geometry import Point, shape
    from shapely.geometry.base import BaseGeometry
    from shapely.wkb import loads as wkbloads
except ImportError:
    logger.warning("Shapely or geojson are not available in the sys path")


class GeoField(fields.Field):
    """The field descriptor contains the field definition common to all
    specialized fields for geolocalization. Subclasses must define a type
    and a geo_type. The type is the name of the corresponding column type,
    the geo_type is the name of the corresponding type in the GIS system.
    """

    geo_type = None
    dim = "2"
    srid = 3857
    gist_index = True

    @property
    def column_type(self):
        postgis_geom_type = self.geo_type.upper() if self.geo_type else "GEOMETRY"
        if self.dim == "3":
            postgis_geom_type += "Z"
        elif self.dim == "4":
            postgis_geom_type += "ZM"
        return ("geometry", f"geometry({postgis_geom_type}, {self.srid})")

    def convert_to_column(self, value, record, values=None, validate=True):
        """Convert value to database format.

        Args:
            value: Can be geojson, wkt, shapely geometry object.
            record: The record being processed.
            values: Additional values dict.
            validate: Whether to perform validation.

        Returns:
            str: WKT string with SRID prefix, or None for empty values.

        Raises:
            ValueError: When geometry validation fails.
            TypeError: When geometry type doesn't match field type.
        """
        if not value:
            return None

        try:
            shape_to_write = self.entry_to_shape(value, same_type=True)
        except (ValueError, TypeError) as e:
            raise ValueError(_("Invalid geometry data: %s") % str(e)) from e

        if shape_to_write.is_empty:
            return None

        # Validate geometry if validation is enabled
        if validate and hasattr(record, "env"):
            config = record.env["ir.config_parameter"].sudo()
            if config.get_param("base_geoengine.validate_geometry", "True") == "True":
                if not shape_to_write.is_valid:
                    raise ValueError(
                        _("Invalid geometry: %s") % shape_to_write.is_valid_reason
                        or "Unknown error"
                    )

                max_size = int(
                    config.get_param("base_geoengine.max_geometry_size", "1000000")
                )
                wkt_size = len(shape_to_write.wkt.encode("utf-8"))
                if wkt_size > max_size:
                    raise ValueError(
                        _("Geometry size (%d bytes) exceeds maximum allowed (%d bytes)")
                        % (wkt_size, max_size)
                    )

        return f"SRID={self.srid};{shape_to_write.wkt}"

    def convert_to_cache(self, value, record, validate=True):
        """Convert geometry value for caching.

        Args:
            value: Geometry value to cache.
            record: The record being processed.
            validate: Whether to perform validation.

        Returns:
            str: Hexadecimal WKB representation or original value.

        Raises:
            ValueError: When geometry conversion fails.
        """
        val = value
        if isinstance(val, bytes | str):
            try:
                int(val, 16)
            except Exception:
                # not an hex value -> try to load from a string
                # representation of a geometry
                try:
                    value = convert.value_to_shape(value, use_wkb=False)
                except Exception as e:
                    raise ValueError(
                        _("Failed to convert geometry to cache format: %s") % str(e)
                    ) from e
        if isinstance(value, BaseGeometry):
            val = value.wkb_hex
        return val

    def convert_to_record(self, value, record):
        """Convert value for record display.

        Args:
            value: Value which may be:
                - a GeoJSON string when field onchange is triggered
                - a geometry object hexcode from cache
                - a unicode containing dict
            record: The record being processed.

        Returns:
            BaseGeometry or False: Shapely geometry object or False for empty values.

        Raises:
            ValueError: When geometry conversion fails.
        """
        if not value:
            return False
        try:
            return convert.value_to_shape(value, use_wkb=True)
        except Exception as e:
            raise ValueError(
                _("Failed to convert value to geometry: %s") % str(e)
            ) from e

    def convert_to_read(self, value, record, use_display_name=True):
        if not isinstance(value, BaseGeometry):
            # read hexadecimal value from database
            shape = self.load_geo(value)
        else:
            shape = value
        if not shape or shape.is_empty:
            return False
        return geojson.dumps(shape)

    # Field description

    # properties used by get_description()
    _description_dim = property(attrgetter("dim"))
    _description_srid = property(attrgetter("srid"))
    _description_gist_index = property(attrgetter("gist_index"))

    @classmethod
    def load_geo(cls, wkb):
        """Load geometry from WKB binary data into Shapely object.

        Converts Well-Known Binary (WKB) data from the database into
        a Shapely geometry object for use in Python operations.

        Args:
            wkb: WKB data as hex string, bytes, or existing BaseGeometry object.

        Returns:
            BaseGeometry or False: Shapely geometry object or False if no data.
        """
        if isinstance(wkb, BaseGeometry):
            return wkb
        return wkbloads(wkb, hex=True) if wkb else False

    def entry_to_shape(self, value, same_type=False):
        """Transform input into a geometry object.

        Args:
            value: Input geometry value in various formats.
            same_type: Whether to enforce geometry type matching.

        Returns:
            BaseGeometry: Shapely geometry object.

        Raises:
            TypeError: When geometry type doesn't match field type.
            ValueError: When geometry data is invalid.
        """
        use_wkb = True
        if isinstance(value, (bytes, str)):
            try:
                int(value, 16)
            except Exception:
                # not an hex value -> try to load from a string
                # representation of a geometry
                use_wkb = False

        try:
            shape = convert.value_to_shape(value, use_wkb=use_wkb)
        except Exception as e:
            raise ValueError(_("Invalid geometry data: %s") % str(e)) from e

        if same_type and not shape.is_empty:
            if shape.geom_type.lower() != self.geo_type.lower():
                raise TypeError(
                    _(
                        "Geometry type mismatch: expected %(expected)s, got %(actual)s",
                        expected=self.geo_type.lower(),
                        actual=shape.geom_type.lower(),
                    )
                )
        return shape

    def update_geo_db_column(self, model):
        """Update the column type in the database."""
        cr = model._cr
        query = """
            SELECT srid, type, coord_dimension
            FROM geometry_columns
            WHERE f_table_name = %s
            AND f_geometry_column = %s
        """
        cr.execute(query, (model._table, self.name))
        check_data = cr.fetchone()
        if not check_data:
            raise TypeError(
                _(
                    "geometry_columns table seems to be corrupted."
                    " SRID check is not possible"
                )
            )
        if check_data[0] != self.srid:
            raise TypeError(
                _(
                    "Reprojection of column is not implemented."
                    " We can not change srid %(srid)s to %(data)s",
                    srid=self.srid,
                    data=check_data[0],
                )
            )
        elif check_data[1] != self.geo_type.upper():
            raise TypeError(
                _(
                    "Geo type modification is not implemented."
                    " We can not change type %(data)s to %(geo_type)s",
                    data=check_data[1],
                    geo_type=self.geo_type.upper(),
                )
            )
        elif check_data[2] != self.dim:
            raise TypeError(
                _(
                    "Geo dimention modification is not implemented."
                    " We can not change dimention %(data)s to %(dim)s",
                    data=check_data[2],
                    dim=self.dim,
                )
            )
        if self.gist_index:
            create_geo_index(cr, self.name, model._table)
        return True

    def update_db_column(self, model, column):
        """Create/update the column corresponding to ``self``.

        For creation of geo column

        :param model: an instance of the field's model
        :param column: the column's configuration (dict)
                       if it exists, or ``None``
        """
        # the column does not exist, create it
        if not column:
            create_geo_column(
                model._cr,
                model._table,
                self.name,
                self.geo_type.upper(),
                self.srid,
                self.dim,
                self.string,
            )
            if self.gist_index:
                create_geo_index(model._cr, self.name, model._table)
            return

        if column["udt_name"] == self.column_type[0]:
            if self.gist_index:
                create_geo_index(model._cr, self.name, model._table)
            return

        self.update_geo_db_column(model)

        if column["udt_name"] in self.column_cast_from:
            sql.convert_column(model._cr, model._table, self.name, self.column_type[1])
        else:
            newname = (self.name + "_moved{}").format
            i = 0
            while sql.column_exists(model._cr, model._table, newname(i)):
                i += 1
            if column["is_nullable"] == "NO":
                sql.drop_not_null(model._cr, model._table, self.name)
            sql.rename_column(model._cr, model._table, self.name, newname(i))
            sql.create_column(
                model._cr, model._table, self.name, self.column_type[1], self.string
            )


class GeoLine(GeoField):
    """PostGIS LineString geometry field for linear features.

    Represents linear geometries such as roads, rivers, boundaries, or any
    feature that can be described as a connected series of points.
    """

    type = "geo_line"
    geo_type = "LineString"

    @classmethod
    def from_points(cls, cr, point1, point2, srid=None):
        """Create a LineString geometry from two Point geometries.

        Uses PostGIS ST_MakeLine function to generate a line connecting
        two points with proper spatial reference system handling.

        Args:
            cr: Database cursor for executing PostGIS operations.
            point1 (BaseGeometry): First point of the line.
            point2 (BaseGeometry): Second point of the line.
            srid (int, optional): Spatial Reference System ID. Uses field default if None.

        Returns:
            BaseGeometry: LineString geometry object connecting the two points.
        """
        query = """
            SELECT
                ST_MakeLine(
                    ST_GeomFromText(%(wkt1)s, %(srid)s),
                    ST_GeomFromText(%(wkt2)s, %(srid)s)
                )
        """
        cr.execute(
            query,
            {
                "wkt1": point1.wkt,
                "wkt2": point2.wkt,
                "srid": srid or cls.srid,
            },
        )
        res = cr.fetchone()
        return cls.load_geo(res[0])


class GeoPoint(GeoField):
    """PostGIS Point geometry field for point features.

    Represents point geometries such as locations, facilities, landmarks,
    or any feature that can be described by a single coordinate pair.
    """

    type = "geo_point"
    geo_type = "Point"

    @classmethod
    def from_latlon(cls, cr, latitude, longitude):
        """Convert WGS84 latitude/longitude coordinates to projected Point geometry.

        Transforms geographic coordinates (WGS84, EPSG:4326) into the field's
        coordinate system using PostGIS transformation functions.

        Args:
            cr: Database cursor for executing PostGIS operations.
            latitude (float): Latitude in decimal degrees (WGS84).
            longitude (float): Longitude in decimal degrees (WGS84).

        Returns:
            BaseGeometry: Point geometry in the field's coordinate system.
        """
        pt = Point(longitude, latitude)
        query = """
            SELECT
                ST_Transform(
                    ST_GeomFromText(%(wkt)s, 4326),
                    %(srid)s
                )
        """
        cr.execute(
            query,
            {
                "wkt": pt.wkt,
                "srid": cls.srid,
            },
        )
        res = cr.fetchone()
        return cls.load_geo(res[0])

    @classmethod
    def to_latlon(cls, cr, geopoint):
        """Convert projected Point geometry to WGS84 latitude/longitude coordinates.

        Transforms a point from the field's coordinate system back to geographic
        coordinates (WGS84, EPSG:4326) for display or export purposes.

        Args:
            cr: Database cursor for executing PostGIS operations.
            geopoint: Point geometry object or GeoJSON string to convert.

        Returns:
            tuple: (longitude, latitude) in decimal degrees (WGS84).
        """
        if isinstance(geopoint, BaseGeometry):
            geo_point_instance = geopoint
        else:
            geo_point_instance = shape(json.loads(geopoint))
        cr.execute(
            """
            SELECT
                ST_TRANSFORM(
                    ST_SetSRID(
                        ST_MakePoint(
                            %(coord_x)s, %(coord_y)s
                        ),
                        %(srid)s
                    ),
                    4326
                )
            """,
            {
                "coord_x": geo_point_instance.x,
                "coord_y": geo_point_instance.y,
                "srid": cls.srid,
            },
        )
        res = cr.fetchone()
        point_latlon = cls.load_geo(res[0])
        return point_latlon.x, point_latlon.y


class GeoPolygon(GeoField):
    """PostGIS Polygon geometry field for area features.

    Represents polygonal geometries such as parcels, buildings, administrative
    boundaries, or any feature that encloses an area.
    """

    type = "geo_polygon"
    geo_type = "Polygon"


class GeoMultiLine(GeoField):
    """PostGIS MultiLineString geometry field for multiple linear features.

    Represents collections of disconnected linear geometries, such as
    multiple road segments or river systems within a single feature.
    """

    type = "geo_multi_line"
    geo_type = "MultiLineString"


class GeoMultiPoint(GeoField):
    """PostGIS MultiPoint geometry field for multiple point features.

    Represents collections of point geometries, such as multiple locations
    or facilities that belong to a single logical entity.
    """

    type = "geo_multi_point"
    geo_type = "MultiPoint"


class GeoMultiPolygon(GeoField):
    """PostGIS MultiPolygon geometry field for multiple area features.

    Represents collections of polygonal geometries, such as archipelagos,
    multi-parcel properties, or administrative regions with multiple areas.
    """

    type = "geo_multi_polygon"
    geo_type = "MultiPolygon"


fields.GeoLine = GeoLine
fields.GeoPoint = GeoPoint
fields.GeoPolygon = GeoPolygon
fields.GeoMultiLine = GeoMultiLine
fields.GeoMultiPoint = GeoMultiPoint
fields.GeoMultiPolygon = GeoMultiPolygon
