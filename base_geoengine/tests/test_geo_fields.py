# Copyright 2025 AgroMarin
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import common, tagged

try:
    import geojson
    from shapely.geometry import Point, LineString, Polygon
    from shapely.wkb import loads as wkbloads

    HAS_GEOSPATIAL = True
except ImportError:
    HAS_GEOSPATIAL = False

from odoo.addons.base_geoengine import fields as geo_fields


@tagged("post_install", "-at_install")
class TestGeoFields(common.TransactionCase):
    """Test geo field functionality and ORM integration."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not HAS_GEOSPATIAL:
            cls.skipTest(cls, "Geospatial libraries not available")

        # Create a test model with all geo field types
        cls.TestModel = cls.env["ir.model"].create(
            {"name": "Test Geo Model", "model": "test.geo.model", "state": "manual"}
        )

        # Create test fields for each geo field type
        cls.test_fields = {}
        geo_types = [
            ("point_field", "geo_point", "GeoPoint"),
            ("line_field", "geo_line", "GeoLine"),
            ("polygon_field", "geo_polygon", "GeoPolygon"),
            ("multipoint_field", "geo_multi_point", "GeoMultiPoint"),
            ("multiline_field", "geo_multi_line", "GeoMultiLine"),
            ("multipolygon_field", "geo_multi_polygon", "GeoMultiPolygon"),
        ]

        for field_name, field_type, field_class in geo_types:
            field = cls.env["ir.model.fields"].create(
                {
                    "name": field_name,
                    "field_description": f"Test {field_class}",
                    "model_id": cls.TestModel.id,
                    "ttype": field_type,
                    "state": "manual",
                }
            )
            cls.test_fields[field_name] = field

    def test_geo_field_registration(self):
        """Test that geo fields are properly registered in Odoo fields namespace."""
        from odoo import fields

        # Verify all geo field types are available
        self.assertTrue(hasattr(fields, "GeoPoint"))
        self.assertTrue(hasattr(fields, "GeoLine"))
        self.assertTrue(hasattr(fields, "GeoPolygon"))
        self.assertTrue(hasattr(fields, "GeoMultiPoint"))
        self.assertTrue(hasattr(fields, "GeoMultiLine"))
        self.assertTrue(hasattr(fields, "GeoMultiPolygon"))

        # Verify they are subclasses of GeoField
        self.assertTrue(issubclass(fields.GeoPoint, geo_fields.GeoField))
        self.assertTrue(issubclass(fields.GeoLine, geo_fields.GeoField))
        self.assertTrue(issubclass(fields.GeoPolygon, geo_fields.GeoField))

    def test_geo_field_column_types(self):
        """Test that geo fields generate correct PostGIS column types."""
        # Test each geo field type
        point_field = geo_fields.GeoPoint()
        self.assertEqual(point_field.column_type, ("geometry", "geometry(POINT, 3857)"))

        line_field = geo_fields.GeoLine()
        self.assertEqual(
            line_field.column_type, ("geometry", "geometry(LINESTRING, 3857)")
        )

        polygon_field = geo_fields.GeoPolygon()
        self.assertEqual(
            polygon_field.column_type, ("geometry", "geometry(POLYGON, 3857)")
        )

        # Test 3D geometry
        point_3d = geo_fields.GeoPoint(dim="3")
        self.assertEqual(point_3d.column_type, ("geometry", "geometry(POINTZ, 3857)"))

        # Test custom SRID
        point_wgs84 = geo_fields.GeoPoint(srid=4326)
        self.assertEqual(point_wgs84.column_type, ("geometry", "geometry(POINT, 4326)"))

    def test_geometry_conversion_wkt(self):
        """Test WKT geometry conversion."""
        point_field = geo_fields.GeoPoint()

        # Test WKT input
        wkt_point = "POINT(746676.106813609 5865349.7175855)"
        shape = point_field.entry_to_shape(wkt_point)

        self.assertIsInstance(shape, Point)
        self.assertAlmostEqual(shape.x, 746676.106813609, places=5)
        self.assertAlmostEqual(shape.y, 5865349.7175855, places=5)

    def test_geometry_conversion_geojson(self):
        """Test GeoJSON geometry conversion."""
        point_field = geo_fields.GeoPoint()

        # Test GeoJSON input
        geojson_point = {
            "type": "Point",
            "coordinates": [746676.106813609, 5865349.7175855],
        }
        shape = point_field.entry_to_shape(json.dumps(geojson_point))

        self.assertIsInstance(shape, Point)
        self.assertAlmostEqual(shape.x, 746676.106813609, places=5)
        self.assertAlmostEqual(shape.y, 5865349.7175855, places=5)

    def test_geometry_conversion_shapely(self):
        """Test Shapely geometry object conversion."""
        point_field = geo_fields.GeoPoint()

        # Test Shapely Point input
        shapely_point = Point(746676.106813609, 5865349.7175855)
        shape = point_field.entry_to_shape(shapely_point)

        self.assertIsInstance(shape, Point)
        self.assertEqual(shape, shapely_point)

    def test_convert_to_column_with_validation(self):
        """Test database column conversion with validation."""
        point_field = geo_fields.GeoPoint()

        # Create mock record for validation
        mock_record = type("MockRecord", (), {})()
        mock_record.env = self.env

        # Test valid geometry
        point = Point(746676.106813609, 5865349.7175855)
        result = point_field.convert_to_column(point, mock_record, validate=True)

        self.assertTrue(result.startswith("SRID=3857;"))
        self.assertIn("POINT", result)

    def test_convert_to_column_empty_values(self):
        """Test conversion of empty/null values."""
        point_field = geo_fields.GeoPoint()
        mock_record = type("MockRecord", (), {})()

        # Test None
        self.assertIsNone(point_field.convert_to_column(None, mock_record))

        # Test empty string
        self.assertIsNone(point_field.convert_to_column("", mock_record))

        # Test empty geometry
        empty_point = Point()  # Creates empty point
        result = point_field.convert_to_column(empty_point, mock_record)
        self.assertIsNone(result)

    def test_convert_to_read_geojson(self):
        """Test conversion to GeoJSON for reading."""
        point_field = geo_fields.GeoPoint()

        # Test with Shapely geometry
        point = Point(746676.106813609, 5865349.7175855)
        result = point_field.convert_to_read(point, None)

        # Should return GeoJSON string
        self.assertIsInstance(result, str)
        parsed = json.loads(result)
        self.assertEqual(parsed["type"], "Point")
        self.assertEqual(len(parsed["coordinates"]), 2)

    def test_type_validation(self):
        """Test geometry type validation."""
        point_field = geo_fields.GeoPoint()

        # Test correct type
        point = Point(746676.106813609, 5865349.7175855)
        shape = point_field.entry_to_shape(point, same_type=True)
        self.assertIsInstance(shape, Point)

        # Test incorrect type
        line = LineString([(0, 0), (1, 1)])
        with self.assertRaises(TypeError):
            point_field.entry_to_shape(line, same_type=True)

    def test_srid_handling(self):
        """Test SRID handling in different coordinate systems."""
        # WGS84 field
        wgs84_field = geo_fields.GeoPoint(srid=4326)
        self.assertEqual(wgs84_field.srid, 4326)

        # Web Mercator field (default)
        mercator_field = geo_fields.GeoPoint()
        self.assertEqual(mercator_field.srid, 3857)

        # Custom SRID
        custom_field = geo_fields.GeoPoint(srid=2154)  # RGF93 Lambert 93
        self.assertEqual(custom_field.srid, 2154)

    def test_dimension_handling(self):
        """Test 2D, 3D, and 4D geometry support."""
        # 2D (default)
        field_2d = geo_fields.GeoPoint()
        self.assertEqual(field_2d.dim, "2")
        self.assertEqual(field_2d.column_type[1], "geometry(POINT, 3857)")

        # 3D
        field_3d = geo_fields.GeoPoint(dim="3")
        self.assertEqual(field_3d.dim, "3")
        self.assertEqual(field_3d.column_type[1], "geometry(POINTZ, 3857)")

        # 4D
        field_4d = geo_fields.GeoPoint(dim="4")
        self.assertEqual(field_4d.dim, "4")
        self.assertEqual(field_4d.column_type[1], "geometry(POINTZM, 3857)")

    def test_geopoint_helper_methods(self):
        """Test GeoPoint helper methods for coordinate conversion."""
        # Mock database cursor
        mock_cr = type("MockCursor", (), {})()
        executed_queries = []
        executed_params = []

        def mock_execute(query, params=None):
            executed_queries.append(query)
            executed_params.append(params)

        def mock_fetchone():
            # Return a mock WKB result
            return ["0101000020110F0000000000000000F03F0000000000000040"]

        mock_cr.execute = mock_execute
        mock_cr.fetchone = mock_fetchone

        with patch.object(geo_fields.GeoPoint, "load_geo", return_value=Point(1, 2)):
            result = geo_fields.GeoPoint.from_latlon(mock_cr, 46.5197, 6.6323)

            # Verify SQL query was executed
            self.assertTrue(any("ST_Transform" in query for query in executed_queries))
            self.assertTrue(
                any("ST_GeomFromText" in query for query in executed_queries)
            )

    def test_error_handling(self):
        """Test error handling for invalid geometry data."""
        point_field = geo_fields.GeoPoint()

        # Test invalid WKT
        with self.assertRaises(ValueError):
            point_field.entry_to_shape("INVALID WKT")

        # Test invalid GeoJSON
        with self.assertRaises(ValueError):
            point_field.entry_to_shape('{"type": "InvalidType"}')

    def test_fields_get_integration(self):
        """Test integration with Odoo's fields_get method."""
        # This tests the fields_get override in base.py
        from odoo.addons.base_geoengine.models.base import Base

        # Mock model with geo field
        mock_model = type(
            "MockModel",
            (Base,),
            {
                "_name": "test.model",
                "_fields": {
                    "test_point": geo_fields.GeoPoint(),
                },
            },
        )()
        mock_model.env = self.env

        # Test fields_get with geo field
        result = mock_model.fields_get(["test_point"])

        self.assertIn("test_point", result)
        field_info = result["test_point"]
        self.assertIn("geo_type", field_info)
        geo_type_info = field_info["geo_type"]
        self.assertEqual(geo_type_info["type"], "geo_point")
        self.assertEqual(geo_type_info["srid"], 3857)
        self.assertEqual(geo_type_info["dim"], 2)

    def test_field_description_properties(self):
        """Test field description properties."""
        point_field = geo_fields.GeoPoint(dim="3", srid=4326, gist_index=False)

        # Test property accessors
        self.assertEqual(point_field._description_dim, "3")
        self.assertEqual(point_field._description_srid, 4326)
        self.assertEqual(point_field._description_gist_index, False)
