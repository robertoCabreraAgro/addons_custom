# Copyright 2025 AgroMarin
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest.mock import Mock, patch

from odoo.tests import common, tagged

try:
    from shapely.geometry import Point, LineString, Polygon

    HAS_GEOSPATIAL = True
except ImportError:
    HAS_GEOSPATIAL = False

from odoo.addons.base_geoengine import fields as geo_fields
from odoo.addons.base_geoengine.geo_operators import GeoOperator


@tagged("post_install", "-at_install")
class TestGeoOperators(common.TransactionCase):
    """Test spatial operators and SQL generation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not HAS_GEOSPATIAL:
            cls.skipTest(cls, "Geospatial libraries not available")

    def setUp(self):
        super().setUp()
        self.point_field = geo_fields.GeoPoint()
        self.polygon_field = geo_fields.GeoPolygon()
        self.geo_operator_point = GeoOperator(self.point_field)
        self.geo_operator_polygon = GeoOperator(self.polygon_field)

        # Test geometries
        self.test_point = Point(746676.106813609, 5865349.7175855)
        self.test_polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        self.test_line = LineString([(0, 0), (1, 1), (2, 2)])

    def test_geo_operator_initialization(self):
        """Test GeoOperator initialization."""
        operator = GeoOperator(self.point_field)
        self.assertEqual(operator.geo_field, self.point_field)

    def test_geo_greater_sql_numeric(self):
        """Test geo_greater SQL generation with numeric value."""
        table = "test_table"
        col = "test_col"
        value = 1000.0
        params = []

        sql = self.geo_operator_point.get_geo_greater_sql(table, col, value, params)

        expected_sql = " ST_Area(test_table.test_col) > 1000.0"
        self.assertEqual(sql, expected_sql)
        self.assertEqual(len(params), 0)  # Numeric values don't add params

    def test_geo_greater_sql_geometry(self):
        """Test geo_greater SQL generation with geometry value."""
        table = "test_table"
        col = "test_col"
        value = self.test_polygon
        params = []

        with patch.object(
            self.point_field, "entry_to_shape", return_value=self.test_polygon
        ):
            sql = self.geo_operator_point.get_geo_greater_sql(table, col, value, params)

        expected_sql = " ST_Area(test_table.test_col) > ST_Area(ST_GeomFromText(%s))"
        self.assertEqual(sql, expected_sql)
        self.assertEqual(len(params), 1)  # WKT added to params
        self.assertEqual(params[0], self.test_polygon.wkt)

    def test_geo_lesser_sql(self):
        """Test geo_lesser SQL generation."""
        table = "test_table"
        col = "test_col"
        value = 500.0
        params = []

        sql = self.geo_operator_point.get_geo_lesser_sql(table, col, value, params)

        expected_sql = " ST_Area(test_table.test_col) < 500.0"
        self.assertEqual(sql, expected_sql)

    def test_geo_equal_sql(self):
        """Test geo_equal SQL generation."""
        table = "test_table"
        col = "test_col"
        value = self.test_point
        params = []

        with patch.object(
            self.point_field, "entry_to_shape", return_value=self.test_point
        ):
            sql = self.geo_operator_point.get_geo_equal_sql(table, col, value, params)

        expected_sql = " test_table.test_col = ST_GeomFromText(%s)"
        self.assertEqual(sql, expected_sql)
        self.assertEqual(len(params), 1)
        self.assertEqual(params[0], self.test_point.wkt)

    def test_geo_intersect_sql(self):
        """Test geo_intersect SQL generation."""
        table = "test_table"
        col = "test_col"
        value = self.test_polygon
        params = []

        with patch.object(
            self.point_field, "entry_to_shape", return_value=self.test_polygon
        ):
            sql = self.geo_operator_point.get_geo_intersect_sql(
                table, col, value, params
            )

        expected_sql = "ST_Intersects(test_table.test_col, ST_GeomFromText(%s, %s))"
        self.assertEqual(sql, expected_sql)
        self.assertEqual(len(params), 2)  # WKT and SRID
        self.assertEqual(params[0], self.test_polygon.wkt)
        self.assertEqual(params[1], self.point_field.srid)

    def test_geo_contains_sql(self):
        """Test geo_contains SQL generation."""
        table = "test_table"
        col = "test_col"
        value = self.test_point
        params = []

        with patch.object(
            self.polygon_field, "entry_to_shape", return_value=self.test_point
        ):
            sql = self.geo_operator_polygon.get_geo_contains_sql(
                table, col, value, params
            )

        expected_sql = "ST_Contains(test_table.test_col, ST_GeomFromText(%s, %s))"
        self.assertEqual(sql, expected_sql)
        self.assertEqual(len(params), 2)
        self.assertEqual(params[0], self.test_point.wkt)
        self.assertEqual(params[1], self.polygon_field.srid)

    def test_geo_within_sql(self):
        """Test geo_within SQL generation."""
        table = "test_table"
        col = "test_col"
        value = self.test_polygon
        params = []

        with patch.object(
            self.point_field, "entry_to_shape", return_value=self.test_polygon
        ):
            sql = self.geo_operator_point.get_geo_within_sql(table, col, value, params)

        expected_sql = "ST_Within(test_table.test_col, ST_GeomFromText(%s, %s))"
        self.assertEqual(sql, expected_sql)
        self.assertEqual(len(params), 2)

    def test_geo_touch_sql(self):
        """Test geo_touch SQL generation."""
        table = "test_table"
        col = "test_col"
        value = self.test_polygon
        params = []

        with patch.object(
            self.point_field, "entry_to_shape", return_value=self.test_polygon
        ):
            sql = self.geo_operator_point.get_geo_touch_sql(table, col, value, params)

        expected_sql = "ST_Touches(test_table.test_col, ST_GeomFromText(%s, %s))"
        self.assertEqual(sql, expected_sql)
        self.assertEqual(len(params), 2)

    def test_different_srid_handling(self):
        """Test SQL generation with different SRID values."""
        # Create field with custom SRID
        custom_field = geo_fields.GeoPoint(srid=4326)
        operator = GeoOperator(custom_field)

        table = "test_table"
        col = "test_col"
        value = self.test_point
        params = []

        with patch.object(custom_field, "entry_to_shape", return_value=self.test_point):
            sql = operator.get_geo_intersect_sql(table, col, value, params)

        # Should use the field's SRID (4326)
        self.assertEqual(params[1], 4326)

    def test_complex_geometry_handling(self):
        """Test operators with complex geometries."""
        # Test with LineString
        line_field = geo_fields.GeoLine()
        line_operator = GeoOperator(line_field)

        table = "test_table"
        col = "line_col"
        value = self.test_line
        params = []

        with patch.object(line_field, "entry_to_shape", return_value=self.test_line):
            sql = line_operator.get_geo_intersect_sql(table, col, value, params)

        expected_sql = "ST_Intersects(test_table.line_col, ST_GeomFromText(%s, %s))"
        self.assertEqual(sql, expected_sql)
        self.assertIn(self.test_line.wkt, params)

    def test_parameter_binding_safety(self):
        """Test that parameters are properly bound to prevent SQL injection."""
        table = "test_table"
        col = "test_col"
        # Malicious input attempt
        value = self.test_point
        params = []

        with patch.object(self.point_field, "entry_to_shape", return_value=value):
            sql = self.geo_operator_point.get_geo_contains_sql(
                table, col, value, params
            )

        # SQL should contain parameter placeholders, not direct values
        self.assertIn("%s", sql)
        self.assertNotIn("DROP TABLE", sql)  # Should not contain injection attempts
        self.assertNotIn(str(value.x), sql)  # Coordinates should be parameterized

    def test_empty_geometry_handling(self):
        """Test operators with empty geometries."""
        empty_point = Point()  # Empty point
        table = "test_table"
        col = "test_col"
        params = []

        with patch.object(self.point_field, "entry_to_shape", return_value=empty_point):
            sql = self.geo_operator_point.get_geo_equal_sql(
                table, col, empty_point, params
            )

        # Should still generate valid SQL
        expected_sql = " test_table.test_col = ST_GeomFromText(%s)"
        self.assertEqual(sql, expected_sql)
        self.assertEqual(len(params), 1)

    def test_operator_method_coverage(self):
        """Test that all operator methods are implemented and callable."""
        operators = [
            "get_geo_greater_sql",
            "get_geo_lesser_sql",
            "get_geo_equal_sql",
            "get_geo_intersect_sql",
            "get_geo_contains_sql",
            "get_geo_within_sql",
            "get_geo_touch_sql",
        ]

        for op_method in operators:
            self.assertTrue(hasattr(self.geo_operator_point, op_method))
            method = getattr(self.geo_operator_point, op_method)
            self.assertTrue(callable(method))

    def test_numeric_vs_geometry_distinction(self):
        """Test that operators correctly distinguish between numeric and geometry values."""
        table = "test_table"
        col = "test_col"

        # Test with integer
        params_int = []
        sql_int = self.geo_operator_point.get_geo_greater_sql(
            table, col, 100, params_int
        )
        self.assertIn("100", sql_int)
        self.assertEqual(len(params_int), 0)

        # Test with float
        params_float = []
        sql_float = self.geo_operator_point.get_geo_greater_sql(
            table, col, 100.5, params_float
        )
        self.assertIn("100.5", sql_float)
        self.assertEqual(len(params_float), 0)

        # Test with geometry (should use parameters)
        params_geom = []
        with patch.object(
            self.point_field, "entry_to_shape", return_value=self.test_point
        ):
            sql_geom = self.geo_operator_point.get_geo_greater_sql(
                table, col, self.test_point, params_geom
            )
        self.assertIn("%s", sql_geom)
        self.assertEqual(len(params_geom), 1)
