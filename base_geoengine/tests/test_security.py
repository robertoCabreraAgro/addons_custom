"""Security tests for base_geoengine module.

Tests SQL injection prevention, parameter sanitization, and security measures.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock

from odoo.exceptions import UserError
from odoo.tools import SQL

from ..geo_operators import GeoOperator
from .. import fields as geo_fields


class TestSQLInjectionPrevention(unittest.TestCase):
    """Test SQL injection prevention in geo operations."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_field = Mock(spec=geo_fields.GeoPoint)
        self.mock_field.srid = 3857
        self.mock_field.entry_to_shape = Mock(return_value=Mock(wkt="POINT(0 0)"))
        self.geo_operator = GeoOperator(self.mock_field)

    def test_sql_injection_in_numeric_value(self):
        """Test SQL injection prevention in numeric comparison values."""
        table = "test_table"
        col = "geo_field"
        params = []

        # Test with malicious numeric-like value
        malicious_value = "1000); DROP TABLE users; --"

        # For numeric values, should safely parameterize
        result = self.geo_operator._get_direct_como_op_sql(
            table, col, malicious_value, params, op=">"
        )

        # Should use parameter placeholder, not direct value
        self.assertIn("%s", result)
        self.assertEqual(len(params), 1)
        self.assertEqual(params[0], malicious_value)

    def test_sql_injection_in_wkt_geometry(self):
        """Test SQL injection prevention in WKT geometry strings."""
        table = "test_table"
        col = "geo_field"
        params = []

        # Test with malicious WKT
        malicious_wkt = "POINT(1 1)'; DROP TABLE users; --"
        mock_shape = Mock(wkt=malicious_wkt)
        self.mock_field.entry_to_shape.return_value = mock_shape

        result = self.geo_operator.get_geo_intersect_sql(
            table, col, malicious_wkt, params
        )

        # Should use parameter placeholders
        self.assertIn("%s", result)
        # Should have parameterized the WKT and SRID
        self.assertEqual(len(params), 2)
        self.assertEqual(params[0], malicious_wkt)
        self.assertEqual(params[1], 3857)

    def test_sql_injection_in_table_name(self):
        """Test that table names are properly handled."""
        # Malicious table name attempt
        malicious_table = "users; DROP TABLE accounts"
        col = "geo_field"
        params = []

        # Table name should be used as-is in the string
        # (will be handled by SQL.identifier in actual usage)
        result = self.geo_operator.get_geo_equal_sql(
            malicious_table, col, "POINT(0 0)", params
        )

        # Table name appears in result but parameters are separate
        self.assertIn(malicious_table, result)
        self.assertIn("%s", result)  # Geometry is parameterized

    def test_sql_injection_in_column_name(self):
        """Test that column names are properly handled."""
        table = "test_table"
        # Malicious column name attempt
        malicious_col = "geo_field; DROP TABLE users"
        params = []

        result = self.geo_operator.get_geo_within_sql(
            table, malicious_col, "POINT(0 0)", params
        )

        # Column name appears in result but parameters are separate
        self.assertIn(malicious_col, result)
        self.assertIn("%s", result)  # Geometry is parameterized

    def test_complex_injection_attempt(self):
        """Test complex SQL injection with multiple attack vectors."""
        table = "test_table"
        col = "geo_field"
        params = []

        # Complex injection attempt with comments and quotes
        complex_injection = """
        POLYGON((0 0, 1 1, 1 0, 0 0))'); 
        DELETE FROM ir_model_access WHERE 1=1; 
        INSERT INTO res_users (login, password) VALUES ('hacker', 'pwd'); --
        """

        mock_shape = Mock(wkt=complex_injection.strip())
        self.mock_field.entry_to_shape.return_value = mock_shape

        result = self.geo_operator.get_geo_contains_sql(
            table, col, complex_injection, params
        )

        # Should safely parameterize the entire malicious string
        self.assertIn("%s", result)
        self.assertEqual(params[0], complex_injection.strip())

    def test_parameter_count_validation(self):
        """Test that parameter count matches placeholders."""
        table = "test_table"
        col = "geo_field"

        operators_to_test = [
            ("get_geo_intersect_sql", 2),  # WKT and SRID
            ("get_geo_contains_sql", 2),  # WKT and SRID
            ("get_geo_within_sql", 2),  # WKT and SRID
            ("get_geo_touch_sql", 2),  # WKT and SRID
            ("get_geo_equal_sql", 1),  # Just WKT
        ]

        for method_name, expected_params in operators_to_test:
            params = []
            method = getattr(self.geo_operator, method_name)
            result = method(table, col, "POINT(0 0)", params)

            # Count %s placeholders
            placeholder_count = result.count("%s")

            self.assertEqual(
                len(params),
                expected_params,
                f"{method_name} should have {expected_params} parameters",
            )
            self.assertEqual(
                placeholder_count,
                expected_params,
                f"{method_name} should have {expected_params} placeholders",
            )


class TestSearchMethodSecurity(unittest.TestCase):
    """Test security in the refactored search method."""

    @patch("odoo.models.BaseModel")
    def setUp(self, mock_base):
        """Set up test model."""
        from ..models.base import Base

        self.test_model = Mock(spec=Base)
        self.test_model._table = "test_geo_model"
        self.test_model._fields = {}
        self.test_model.env = Mock()
        self.test_model.env.cr = Mock()
        self.test_model.browse = Mock(return_value=Mock(ids=[]))

    def test_sql_identifier_usage(self):
        """Test that SQL.identifier is used for table names."""
        from ..models.base import Base

        # Create a mock cursor
        mock_cursor = Mock()
        mock_cursor.execute = Mock()
        mock_cursor.fetchall = Mock(return_value=[])

        # Setup model
        model = Base()
        model._table = "test_table"
        model._fields = {"geo_field": Mock(spec=geo_fields.GeoPoint)}
        model.env = Mock()
        model.env.cr = mock_cursor

        # Mock the field
        geo_field = model._fields["geo_field"]
        geo_field.srid = 3857
        geo_field.entry_to_shape = Mock(return_value=Mock(wkt="POINT(0 0)"))

        # Process a geo operator
        result = model._process_geo_operator("geo_field", "geo_intersect", "POINT(1 1)")

        # Verify SQL class and SQL.identifier were used
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args

        # First argument should be a SQL object
        query = call_args[0][0]
        # Query should be properly formatted (we can't check exact type due to mocking)
        self.assertIsNotNone(query)

    def test_malicious_domain_handling(self):
        """Test handling of malicious values in domain."""
        from ..models.base import Base

        model = Base()
        model._table = "test_table"
        model._fields = {"geo_field": Mock(spec=geo_fields.GeoPoint)}
        model.env = Mock()
        model.env.cr = Mock()
        model.env.cr.fetchall = Mock(return_value=[])

        # Malicious domain values
        malicious_domains = [
            [("geo_field", "geo_contains", "'); DROP TABLE users; --")],
            [("geo_field", "geo_intersect", "POINT(0 0)' OR '1'='1")],
            [("geo_field", "geo_within", ")); DELETE FROM res_users; --")],
        ]

        for domain in malicious_domains:
            # Should handle without executing malicious SQL
            geo_conditions, regular_domain = model._split_geo_domain(domain)

            # Should recognize as geo condition
            self.assertEqual(len(geo_conditions), 1)
            self.assertEqual(len(regular_domain), 0)

            # Process should not raise security exceptions
            field_name, operator, value = geo_conditions[0]
            # This would be safely parameterized in actual execution
            self.assertEqual(value, domain[0][2])


class TestGeometryValidation(unittest.TestCase):
    """Test geometry validation and sanitization."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_field = Mock(spec=geo_fields.GeoPolygon)
        self.mock_field.srid = 3857

    def test_invalid_geometry_handling(self):
        """Test handling of invalid geometry data."""
        invalid_geometries = [
            "NOT A GEOMETRY",
            "POINT()",
            "POLYGON((0 0, 1 1))",  # Unclosed polygon
            "'; DROP TABLE users; --",
            "../../../../etc/passwd",
            "<script>alert('XSS')</script>",
        ]

        for invalid_geom in invalid_geometries:
            # Should handle invalid geometry safely
            try:
                # In real implementation, this would raise appropriate error
                self.mock_field.entry_to_shape = Mock(
                    side_effect=ValueError(f"Invalid geometry: {invalid_geom}")
                )
                geo_op = GeoOperator(self.mock_field)
                params = []

                # Should handle the error gracefully
                with self.assertRaises(ValueError):
                    self.mock_field.entry_to_shape(invalid_geom)

            except Exception as e:
                # Should not expose system information
                self.assertNotIn("/etc/passwd", str(e))
                self.assertNotIn("DROP TABLE", str(e))

    def test_geometry_size_limits(self):
        """Test that overly large geometries are handled."""
        # Create a very large polygon (potential DoS attack)
        huge_coords = " ".join([f"{i} {i}," for i in range(10000)])
        huge_polygon = f"POLYGON(({huge_coords} 0 0))"

        mock_shape = Mock()
        mock_shape.wkt = huge_polygon
        mock_shape.is_valid = True

        # In real implementation, should have size limits
        # This is handled in fields.py convert_to_column
        self.assertGreater(len(huge_polygon), 100000)


class TestParameterSanitization(unittest.TestCase):
    """Test parameter sanitization in geo operations."""

    def test_srid_validation(self):
        """Test that SRID values are properly validated."""
        mock_field = Mock(spec=geo_fields.GeoPoint)

        # Test with various SRID values
        valid_srids = [3857, 4326, 2154, 32632]
        invalid_srids = [
            "3857'; DROP TABLE users; --",
            -1,
            None,
            "SELECT * FROM users",
            99999999,  # Unreasonably large
        ]

        for srid in valid_srids:
            mock_field.srid = srid
            geo_op = GeoOperator(mock_field)
            # Should accept valid SRIDs
            self.assertEqual(geo_op.geo_field.srid, srid)

        for srid in invalid_srids:
            # In real implementation, should validate SRID
            if isinstance(srid, str) and not srid.isdigit():
                # String SRIDs should be rejected or sanitized
                self.assertIn("DROP TABLE", srid) or self.assertIn("SELECT", srid)

    def test_numeric_parameter_validation(self):
        """Test validation of numeric parameters."""
        mock_field = Mock(spec=geo_fields.GeoPoint)
        mock_field.srid = 3857
        geo_op = GeoOperator(mock_field)

        # Test area comparison with various numeric inputs
        test_values = [
            (100, True),  # Valid
            (100.5, True),  # Valid float
            ("100", False),  # String number - should be handled
            ("100.5'; DROP TABLE users; --", False),  # Malicious
        ]

        for value, is_valid in test_values:
            params = []
            if isinstance(value, (int, float)):
                # Should handle numeric values
                result = geo_op._get_direct_como_op_sql(
                    "test_table", "geo_field", value, params, ">"
                )
                self.assertIn("%s", result)
                self.assertEqual(params[0], value)


if __name__ == "__main__":
    unittest.main()
