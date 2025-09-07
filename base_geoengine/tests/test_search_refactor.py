"""Tests for the refactored search method in base_geoengine.

Tests the new modular search implementation including _process_geo_operator.
"""

import unittest
from unittest.mock import Mock, patch


from .. import fields as geo_fields
from ..models.base import Base


class TestSearchMethodRefactor(unittest.TestCase):
    """Test the refactored search method implementation."""

    def setUp(self):
        """Set up test model and mocks."""
        self.test_model = Mock(spec=Base)
        self.test_model._table = "test_geo_table"
        self.test_model._fields = {
            "geo_point": Mock(spec=geo_fields.GeoPoint),
            "geo_polygon": Mock(spec=geo_fields.GeoPolygon),
            "name": Mock(),  # Regular field
            "active": Mock(),  # Regular field
        }

        # Setup geo fields
        self.test_model._fields["geo_point"].srid = 3857
        self.test_model._fields["geo_polygon"].srid = 3857

        # Mock environment and cursor
        self.test_model.env = Mock()
        self.test_model.env.cr = Mock()
        self.test_model.env.cr.execute = Mock()
        self.test_model.env.cr.fetchall = Mock(return_value=[(1,), (2,), (3,)])

        # Mock browse method
        self.test_model.browse = Mock(return_value=Mock(ids=[1, 2, 3]))

        # Setup GEO_OPERATORS
        self.test_model._GEO_OPERATORS = {
            "geo_greater",
            "geo_lesser",
            "geo_equal",
            "geo_touch",
            "geo_within",
            "geo_contains",
            "geo_intersect",
        }

    def test_process_domain_with_geo_empty(self):
        """Test processing empty domain."""
        model = Base()
        model._GEO_OPERATORS = self.test_model._GEO_OPERATORS

        result = model._process_domain_with_geo([])

        self.assertEqual(result, [])

    def test_process_domain_only_regular(self):
        """Test processing domain with only regular conditions."""
        model = Base()
        model._GEO_OPERATORS = self.test_model._GEO_OPERATORS

        domain = [
            ("name", "=", "Test"),
            ("active", "=", True),
            ("id", "in", [1, 2, 3]),
        ]

        result = model._process_domain_with_geo(domain)

        # Should return domain unchanged since no geo operators
        self.assertEqual(result, domain)

    def test_process_domain_only_geo(self):
        """Test processing domain with only geo conditions."""
        model = Base()
        model._GEO_OPERATORS = self.test_model._GEO_OPERATORS
        model._table = self.test_model._table
        model._fields = self.test_model._fields
        model.env = self.test_model.env

        # Mock _process_geo_operator to return IDs
        model._process_geo_operator = Mock(side_effect=[{1, 2, 3}, {2, 3}])

        domain = [
            ("geo_point", "geo_intersect", "POINT(0 0)"),
            ("geo_polygon", "geo_contains", "POINT(1 1)"),
        ]

        result = model._process_domain_with_geo(domain)

        # Should have converted to ID filters
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0][0], "id")
        self.assertEqual(result[0][1], "in")
        self.assertEqual(result[1][0], "id")
        self.assertEqual(result[1][1], "in")

    def test_process_domain_mixed(self):
        """Test processing domain with mixed conditions."""
        model = Base()
        model._GEO_OPERATORS = self.test_model._GEO_OPERATORS
        model._table = self.test_model._table
        model._fields = self.test_model._fields
        model.env = self.test_model.env

        # Mock _process_geo_operator
        model._process_geo_operator = Mock(side_effect=[{1, 2, 3}, {2, 3, 4}])

        domain = [
            ("name", "=", "Test"),
            ("geo_point", "geo_within", "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"),
            ("active", "=", True),
            ("geo_polygon", "geo_intersect", "POINT(0.5 0.5)"),
            "|",  # OR operator
            ("id", ">", 100),
        ]

        result = model._process_domain_with_geo(domain)

        # Should preserve structure with geo operators converted
        self.assertEqual(len(result), 6)
        self.assertEqual(result[0], ("name", "=", "Test"))
        self.assertEqual(result[1][0], "id")  # Converted geo operator
        self.assertEqual(result[1][1], "in")
        self.assertEqual(result[2], ("active", "=", True))
        self.assertEqual(result[3][0], "id")  # Converted geo operator
        self.assertEqual(result[3][1], "in")
        self.assertEqual(result[4], "|")
        self.assertEqual(result[5], ("id", ">", 100))

    def test_process_geo_operator_valid_field(self):
        """Test processing valid geo operator."""
        model = Base()
        model._table = self.test_model._table
        model._fields = self.test_model._fields
        model.env = self.test_model.env

        # Mock GeoOperator
        with patch("base_geoengine.models.base.GeoOperator") as MockGeoOperator:
            mock_geo_op = MockGeoOperator.return_value
            mock_geo_op.get_geo_intersect_sql = Mock(
                return_value="ST_Intersects(test_geo_table.geo_point, ST_GeomFromText(%s, %s))"
            )

            result = model._process_geo_operator(
                "geo_point", "geo_intersect", "POINT(1 1)"
            )

            # Should return set of IDs
            self.assertIsInstance(result, set)
            self.assertEqual(result, {1, 2, 3})

            # Should have executed query
            model.env.cr.execute.assert_called_once()

    def test_process_geo_operator_invalid_field(self):
        """Test processing geo operator on non-geo field."""
        model = Base()
        model._table = self.test_model._table
        model._fields = self.test_model._fields
        model.env = self.test_model.env

        # Try to use geo operator on regular field
        result = model._process_geo_operator("name", "geo_intersect", "POINT(1 1)")

        # Should return None for non-geo field
        self.assertIsNone(result)

        # Should not execute any query
        model.env.cr.execute.assert_not_called()

    def test_process_geo_operator_unknown_operator(self):
        """Test processing unknown geo operator."""
        model = Base()
        model._table = self.test_model._table
        model._fields = self.test_model._fields
        model.env = self.test_model.env

        # Try unknown operator
        result = model._process_geo_operator("geo_point", "geo_unknown", "POINT(1 1)")

        # Should return None for unknown operator
        self.assertIsNone(result)

        # Should not execute any query
        model.env.cr.execute.assert_not_called()

    def test_process_geo_operator_exception_handling(self):
        """Test exception handling in geo operator processing."""
        model = Base()
        model._table = self.test_model._table
        model._fields = self.test_model._fields
        model.env = self.test_model.env

        # Mock GeoOperator to raise exception
        with patch("base_geoengine.models.base.GeoOperator") as MockGeoOperator:
            MockGeoOperator.side_effect = ValueError("Invalid geometry")

            # Should handle exception and return empty set
            with patch("base_geoengine.models.base.logger") as mock_logger:
                result = model._process_geo_operator(
                    "geo_point", "geo_intersect", "INVALID"
                )

                # Should return empty set on error
                self.assertEqual(result, set())

                # Should log the error
                mock_logger.warning.assert_called()

    def test_search_no_geo_operators(self):
        """Test search method with no geo operators."""
        model = Base()
        model._GEO_OPERATORS = self.test_model._GEO_OPERATORS

        # Mock super().search
        with patch.object(Base, "__bases__", (Mock,)):
            mock_super = Mock()
            mock_super.search = Mock(return_value=Mock(ids=[1, 2, 3]))

            with patch("builtins.super", return_value=mock_super):
                domain = [("name", "=", "Test"), ("active", "=", True)]
                result = model.search(domain, offset=0, limit=10)

                # Should call parent search directly
                mock_super.search.assert_called_once_with(
                    domain, offset=0, limit=10, order=None
                )

    def test_search_with_geo_operators(self):
        """Test search method with geo operators."""
        model = Base()
        model._table = self.test_model._table
        model._fields = self.test_model._fields
        model._GEO_OPERATORS = self.test_model._GEO_OPERATORS
        model.env = self.test_model.env
        model.browse = self.test_model.browse

        # Mock _process_domain_with_geo to return converted domain
        model._process_domain_with_geo = Mock(
            return_value=[
                ("name", "=", "Test"),
                ("id", "in", [1, 2, 3]),  # Converted geo operator
            ]
        )

        # Mock super().search
        with patch.object(Base, "__bases__", (Mock,)):
            mock_super = Mock()
            mock_super.search = Mock(return_value=Mock(ids=[1, 2, 3]))

            with patch("builtins.super", return_value=mock_super):
                domain = [
                    ("name", "=", "Test"),
                    ("geo_point", "geo_intersect", "POINT(0 0)"),
                ]

                result = model.search(domain, offset=10, limit=20, order="name")

                # Should process domain
                model._process_domain_with_geo.assert_called_once_with(domain)

                # Should call super().search with processed domain and params
                mock_super.search.assert_called_once_with(
                    [("name", "=", "Test"), ("id", "in", [1, 2, 3])],
                    offset=10,
                    limit=20,
                    order="name",
                )

    def test_search_with_complex_domain(self):
        """Test search with complex domain including OR and NOT."""
        model = Base()
        model._table = self.test_model._table
        model._fields = self.test_model._fields
        model._GEO_OPERATORS = self.test_model._GEO_OPERATORS
        model.env = self.test_model.env

        # Mock _process_domain_with_geo to simulate complex domain processing
        def mock_process_domain(domain):
            # Simulate converting geo operators while preserving structure
            result = []
            for term in domain:
                if isinstance(term, str):
                    result.append(term)
                elif term[1] in model._GEO_OPERATORS:
                    # Convert geo operator to ID filter
                    result.append(("id", "in", [1, 2, 3]))
                else:
                    result.append(term)
            return result

        model._process_domain_with_geo = mock_process_domain

        # Mock super().search
        with patch.object(Base, "__bases__", (Mock,)):
            mock_super = Mock()
            mock_super.search = Mock(return_value=Mock(ids=[1, 2]))

            with patch("builtins.super", return_value=mock_super):
                # Complex domain with OR and geo operators
                domain = [
                    "|",
                    ("geo_point", "geo_intersect", "POINT(0 0)"),
                    "&",
                    ("name", "=", "Test"),
                    ("geo_polygon", "geo_within", "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"),
                ]

                result = model.search(domain)

                # Should have called super().search with processed domain
                mock_super.search.assert_called_once()
                processed_domain = mock_super.search.call_args[0][0]

                # Domain structure should be preserved
                self.assertEqual(processed_domain[0], "|")
                self.assertEqual(processed_domain[1][0], "id")  # Converted geo
                self.assertEqual(processed_domain[2], "&")
                self.assertEqual(processed_domain[3], ("name", "=", "Test"))
                self.assertEqual(processed_domain[4][0], "id")  # Converted geo

    def test_search_count_with_geo(self):
        """Test search_count with geo operators."""
        model = Base()
        model._table = self.test_model._table
        model._fields = self.test_model._fields
        model._GEO_OPERATORS = self.test_model._GEO_OPERATORS
        model.env = self.test_model.env

        # Mock _process_domain_with_geo
        model._process_domain_with_geo = Mock(return_value=[("id", "in", [1, 2, 3])])

        with patch.object(Base, "__bases__", (Mock,)):
            mock_super = Mock()
            mock_super.search_count = Mock(return_value=3)

            with patch("builtins.super", return_value=mock_super):
                count = model.search_count(
                    [("geo_point", "geo_intersect", "POINT(0 0)")]
                )

                # Should process domain and call super
                model._process_domain_with_geo.assert_called_once()
                mock_super.search_count.assert_called_once_with(
                    [("id", "in", [1, 2, 3])]
                )
                self.assertEqual(count, 3)

    def test_search_read_with_geo(self):
        """Test search_read with geo operators."""
        model = Base()
        model._table = self.test_model._table
        model._fields = self.test_model._fields
        model._GEO_OPERATORS = self.test_model._GEO_OPERATORS
        model.env = self.test_model.env

        # Mock _process_domain_with_geo
        model._process_domain_with_geo = Mock(return_value=[("id", "in", [1, 2])])

        with patch.object(Base, "__bases__", (Mock,)):
            mock_super = Mock()
            mock_super.search_read = Mock(
                return_value=[{"id": 1, "name": "Test 1"}, {"id": 2, "name": "Test 2"}]
            )

            with patch("builtins.super", return_value=mock_super):
                result = model.search_read(
                    [("geo_point", "geo_intersect", "POINT(0 0)")],
                    fields=["name"],
                    offset=0,
                    limit=10,
                    order="name",
                )

                # Should process domain and call super
                model._process_domain_with_geo.assert_called_once()
                mock_super.search_read.assert_called_once_with(
                    domain=[("id", "in", [1, 2])],
                    fields=["name"],
                    offset=0,
                    limit=10,
                    order="name",
                )
                self.assertEqual(len(result), 2)


class TestOperatorMethodMapping(unittest.TestCase):
    """Test the operator method mapping in _process_geo_operator."""

    def setUp(self):
        """Set up test model."""
        self.model = Base()
        self.model._table = "test_table"
        self.model._fields = {"geo_field": Mock(spec=geo_fields.GeoPoint)}
        self.model._fields["geo_field"].srid = 3857
        self.model.env = Mock()
        self.model.env.cr = Mock()
        self.model.env.cr.execute = Mock()
        self.model.env.cr.fetchall = Mock(return_value=[])

    def test_all_operators_mapped(self):
        """Test that all geo operators are properly mapped."""
        operators = [
            "geo_greater",
            "geo_lesser",
            "geo_equal",
            "geo_touch",
            "geo_within",
            "geo_contains",
            "geo_intersect",
        ]

        for operator in operators:
            with self.subTest(operator=operator):
                # Mock GeoOperator for this test
                with patch("base_geoengine.models.base.GeoOperator") as MockGeoOperator:
                    mock_geo_op = MockGeoOperator.return_value
                    # Set up the appropriate method based on operator
                    method_name = f"get_{operator.replace('geo_', 'geo_')}_sql"
                    setattr(mock_geo_op, method_name, Mock(return_value="TRUE"))

                    result = self.model._process_geo_operator(
                        "geo_field", operator, "POINT(1 1)"
                    )

                    # Should return a set (even if empty)
                    self.assertIsInstance(result, set)

                    # Should have attempted to execute a query
                    self.model.env.cr.execute.assert_called()

                    # Reset mock for next iteration
                    self.model.env.cr.execute.reset_mock()


class TestSQLGeneration(unittest.TestCase):
    """Test SQL generation with the refactored method."""

    def setUp(self):
        """Set up test environment."""
        self.model = Base()
        self.model._table = "test_geo_table"
        self.model._fields = {"location": Mock(spec=geo_fields.GeoPoint)}
        self.model._fields["location"].srid = 3857
        self.model._fields["location"].entry_to_shape = Mock(
            return_value=Mock(wkt="POINT(100 200)")
        )
        self.model.env = Mock()
        self.model.env.cr = Mock()

    def test_sql_query_structure(self):
        """Test that generated SQL has correct structure."""
        # Capture the SQL query
        executed_query = None
        executed_params = None

        def capture_execute(query, params=None):
            nonlocal executed_query, executed_params
            executed_query = query
            executed_params = params
            return Mock()

        self.model.env.cr.execute = capture_execute
        self.model.env.cr.fetchall = Mock(return_value=[(1,), (2,)])

        with patch("base_geoengine.models.base.GeoOperator") as MockGeoOperator:
            mock_geo_op = MockGeoOperator.return_value
            mock_geo_op.get_geo_intersect_sql = Mock(
                return_value="ST_Intersects(test_geo_table.location, ST_GeomFromText(%s, %s))"
            )

            result = self.model._process_geo_operator(
                "location", "geo_intersect", "POINT(150 250)"
            )

            # Check that a query was executed
            self.assertIsNotNone(executed_query)
            self.assertIsNotNone(executed_params)

            # Check that GeoOperator was called with correct field
            MockGeoOperator.assert_called_once()

    def test_sql_identifier_safety(self):
        """Test that table names use SQL.identifier."""
        # This test verifies the structure without actual SQL execution
        with patch("base_geoengine.models.base.SQL") as mock_sql:
            # SQL.identifier is a class method
            mock_sql.identifier = Mock(return_value="SAFE_IDENTIFIER")
            mock_sql.return_value = "SAFE_QUERY"

            with patch("base_geoengine.models.base.GeoOperator") as MockGeoOperator:
                mock_geo_op = MockGeoOperator.return_value
                mock_geo_op.get_geo_intersect_sql = Mock(return_value="TRUE")

                self.model.env.cr.fetchall = Mock(return_value=[])

                result = self.model._process_geo_operator(
                    "location", "geo_intersect", "POINT(0 0)"
                )

                # Verify SQL.identifier was called with table name
                mock_sql.identifier.assert_called_with("test_geo_table")

                # Verify SQL was used for query construction
                mock_sql.assert_called()


if __name__ == "__main__":
    unittest.main()
