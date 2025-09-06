"""Tests for the refactored search method in base_geoengine.

Tests the new modular search implementation including _process_geo_operator
and _split_geo_domain methods.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, call

from odoo.exceptions import UserError
from odoo.tools import SQL

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

    def test_split_geo_domain_empty(self):
        """Test splitting empty domain."""
        model = Base()
        model._GEO_OPERATORS = self.test_model._GEO_OPERATORS

        geo_conditions, regular_domain = model._split_geo_domain([])

        self.assertEqual(geo_conditions, [])
        self.assertEqual(regular_domain, [])

    def test_split_geo_domain_only_regular(self):
        """Test splitting domain with only regular conditions."""
        model = Base()
        model._GEO_OPERATORS = self.test_model._GEO_OPERATORS

        domain = [
            ("name", "=", "Test"),
            ("active", "=", True),
            ("id", "in", [1, 2, 3]),
        ]

        geo_conditions, regular_domain = model._split_geo_domain(domain)

        self.assertEqual(geo_conditions, [])
        self.assertEqual(regular_domain, domain)

    def test_split_geo_domain_only_geo(self):
        """Test splitting domain with only geo conditions."""
        model = Base()
        model._GEO_OPERATORS = self.test_model._GEO_OPERATORS

        domain = [
            ("geo_point", "geo_intersect", "POINT(0 0)"),
            ("geo_polygon", "geo_contains", "POINT(1 1)"),
        ]

        geo_conditions, regular_domain = model._split_geo_domain(domain)

        self.assertEqual(len(geo_conditions), 2)
        self.assertEqual(regular_domain, [])
        self.assertEqual(geo_conditions[0], domain[0])
        self.assertEqual(geo_conditions[1], domain[1])

    def test_split_geo_domain_mixed(self):
        """Test splitting domain with mixed conditions."""
        model = Base()
        model._GEO_OPERATORS = self.test_model._GEO_OPERATORS

        domain = [
            ("name", "=", "Test"),
            ("geo_point", "geo_within", "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"),
            ("active", "=", True),
            ("geo_polygon", "geo_intersect", "POINT(0.5 0.5)"),
            "|",  # OR operator
            ("id", ">", 100),
        ]

        geo_conditions, regular_domain = model._split_geo_domain(domain)

        self.assertEqual(len(geo_conditions), 2)
        self.assertEqual(len(regular_domain), 4)  # name, active, |, id

        # Check geo conditions
        self.assertIn(
            ("geo_point", "geo_within", "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"),
            geo_conditions,
        )
        self.assertIn(
            ("geo_polygon", "geo_intersect", "POINT(0.5 0.5)"), geo_conditions
        )

        # Check regular domain preserved order
        self.assertEqual(regular_domain[0], ("name", "=", "Test"))
        self.assertEqual(regular_domain[1], ("active", "=", True))
        self.assertEqual(regular_domain[2], "|")
        self.assertEqual(regular_domain[3], ("id", ">", 100))

    def test_process_geo_operator_valid_field(self):
        """Test processing valid geo operator."""
        model = Base()
        model._table = self.test_model._table
        model._fields = self.test_model._fields
        model.env = self.test_model.env

        # Mock the geo field's entry_to_shape
        mock_shape = Mock(wkt="POINT(0 0)")
        model._fields["geo_point"].entry_to_shape = Mock(return_value=mock_shape)

        result = model._process_geo_operator("geo_point", "geo_intersect", "POINT(1 1)")

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

        # Mock field to raise exception
        model._fields["geo_point"].entry_to_shape = Mock(
            side_effect=ValueError("Invalid geometry")
        )

        # Should handle exception and return empty set
        with patch("logging.getLogger") as mock_logger:
            result = model._process_geo_operator(
                "geo_point", "geo_intersect", "INVALID"
            )

            # Should return empty set on error
            self.assertEqual(result, set())

            # Should log the error
            mock_logger.return_value.warning.assert_called()

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

        # Mock methods
        model._split_geo_domain = Mock(
            return_value=(
                [("geo_point", "geo_intersect", "POINT(0 0)")],
                [("name", "=", "Test")],
            )
        )
        model._process_geo_operator = Mock(return_value={1, 2, 3})

        # Mock super().search
        with patch.object(Base, "__bases__", (Mock,)):
            mock_super = Mock()
            mock_super.search = Mock(return_value=Mock(ids=[1, 2, 3, 4, 5]))

            with patch("builtins.super", return_value=mock_super):
                domain = [
                    ("name", "=", "Test"),
                    ("geo_point", "geo_intersect", "POINT(0 0)"),
                ]

                result = model.search(domain)

                # Should split domain
                model._split_geo_domain.assert_called_once_with(domain)

                # Should process geo operator
                model._process_geo_operator.assert_called_once_with(
                    "geo_point", "geo_intersect", "POINT(0 0)"
                )

                # With our new implementation, super().search is called multiple times:
                # 1. First with regular domain to get base records
                # 2. Then with ('id', 'in', final_ids) domain for final result
                self.assertEqual(mock_super.search.call_count, 2)
                
                # First call should be with regular domain
                first_call = mock_super.search.call_args_list[0]
                self.assertEqual(first_call[0][0], [("name", "=", "Test")])
                
                # Second call should include id filter
                second_call = mock_super.search.call_args_list[1]
                domain = second_call[0][0]
                # Should have ('id', 'in', ...) in the domain
                id_conditions = [cond for cond in domain if isinstance(cond, tuple) and cond[0] == 'id']
                self.assertTrue(len(id_conditions) > 0)

    def test_search_intersection_logic(self):
        """Test that geo results are properly intersected."""
        model = Base()
        model._table = self.test_model._table
        model._fields = self.test_model._fields
        model._GEO_OPERATORS = self.test_model._GEO_OPERATORS
        model.env = self.test_model.env

        # Setup multiple geo conditions with different results
        geo_results = [
            {1, 2, 3, 4, 5},  # First geo condition
            {2, 3, 4, 6, 7},  # Second geo condition
            {3, 4, 5, 6, 8},  # Third geo condition
        ]

        model._split_geo_domain = Mock(
            return_value=(
                [
                    ("geo_point", "geo_intersect", "POINT(0 0)"),
                    ("geo_polygon", "geo_contains", "POINT(1 1)"),
                    ("geo_point", "geo_within", "POLYGON((0 0, 2 0, 2 2, 0 2, 0 0))"),
                ],
                [],
            )
        )

        # Mock _process_geo_operator to return different sets
        model._process_geo_operator = Mock(side_effect=geo_results)

        # Mock browse to track final IDs
        model.browse = Mock(return_value=Mock(ids=[]))

        # Mock super().search to return all IDs
        with patch.object(Base, "__bases__", (Mock,)):
            mock_super = Mock()
            mock_super.search = Mock(return_value=Mock(ids=list(range(1, 10))))

            with patch("builtins.super", return_value=mock_super):
                result = model.search(
                    [
                        ("geo_point", "geo_intersect", "POINT(0 0)"),
                        ("geo_polygon", "geo_contains", "POINT(1 1)"),
                        (
                            "geo_point",
                            "geo_within",
                            "POLYGON((0 0, 2 0, 2 2, 0 2, 0 0))",
                        ),
                    ]
                )

                # Should search with intersection of all sets
                # Intersection of {1,2,3,4,5} ∩ {2,3,4,6,7} ∩ {3,4,5,6,8} = {3,4}
                expected_ids = {3, 4}

                # The new implementation calls super().search with ('id', 'in', final_ids)
                # Check the last call to mock_super.search
                final_search_call = mock_super.search.call_args_list[-1]
                domain = final_search_call[0][0]
                
                # The domain should be [('id', 'in', [3, 4])] or [('id', 'in', [4, 3])]
                self.assertEqual(len(domain), 1)
                self.assertEqual(domain[0][0], 'id')
                self.assertEqual(domain[0][1], 'in')
                self.assertEqual(set(domain[0][2]), expected_ids)

    def test_search_with_ordering(self):
        """Test search with order parameter."""
        model = Base()
        model._table = self.test_model._table
        model._fields = self.test_model._fields
        model._GEO_OPERATORS = self.test_model._GEO_OPERATORS
        model.env = self.test_model.env

        # Mock recordset with sortable items
        mock_records = Mock()
        mock_records.sorted = Mock(return_value=mock_records)
        mock_records.__getitem__ = Mock(return_value=mock_records)
        model.browse = Mock(return_value=mock_records)

        model._split_geo_domain = Mock(
            return_value=([("geo_point", "geo_intersect", "POINT(0 0)")], [])
        )
        model._process_geo_operator = Mock(return_value={1, 2, 3})

        with patch.object(Base, "__bases__", (Mock,)):
            mock_super = Mock()
            mock_super.search = Mock(return_value=Mock(ids=[1, 2, 3]))

            with patch("builtins.super", return_value=mock_super):
                result = model.search(
                    [("geo_point", "geo_intersect", "POINT(0 0)")], order="name desc"
                )

                # With new implementation, ordering is passed to super().search
                # Check that the final search call includes the order parameter
                final_call = mock_super.search.call_args_list[-1]
                self.assertEqual(final_call[1].get('order'), "name desc")

    def test_search_with_offset_limit(self):
        """Test search with offset and limit parameters."""
        model = Base()
        model._table = self.test_model._table
        model._fields = self.test_model._fields
        model._GEO_OPERATORS = self.test_model._GEO_OPERATORS
        model.env = self.test_model.env

        # Mock recordset with slicing support
        mock_records = Mock()
        mock_records.__getitem__ = Mock(return_value=mock_records)
        model.browse = Mock(return_value=mock_records)

        model._split_geo_domain = Mock(
            return_value=([("geo_point", "geo_intersect", "POINT(0 0)")], [])
        )
        model._process_geo_operator = Mock(return_value={1, 2, 3, 4, 5})

        with patch.object(Base, "__bases__", (Mock,)):
            mock_super = Mock()
            mock_super.search = Mock(return_value=Mock(ids=list(range(1, 10))))

            with patch("builtins.super", return_value=mock_super):
                result = model.search(
                    [("geo_point", "geo_intersect", "POINT(0 0)")], offset=2, limit=3
                )

                # With new implementation, offset and limit are passed to super().search
                # Check that the final search call includes offset and limit
                final_call = mock_super.search.call_args_list[-1]
                self.assertEqual(final_call[1].get('offset'), 2)
                self.assertEqual(final_call[1].get('limit'), 3)


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
                # Mock the field's entry_to_shape
                self.model._fields["geo_field"].entry_to_shape = Mock(
                    return_value=Mock(wkt="POINT(0 0)")
                )

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

        result = self.model._process_geo_operator(
            "location", "geo_intersect", "POINT(150 250)"
        )

        # Check that a query was executed
        self.assertIsNotNone(executed_query)
        self.assertIsNotNone(executed_params)

        # Check that params contain the geometry data
        self.assertEqual(len(executed_params), 2)  # WKT and SRID
        self.assertEqual(executed_params[0], "POINT(150 250)")
        self.assertEqual(executed_params[1], 3857)

    def test_sql_identifier_safety(self):
        """Test that table names use SQL.identifier."""
        # This test verifies the structure without actual SQL execution
        with patch("odoo.tools.SQL") as mock_sql:
            # SQL.identifier is a class method
            mock_sql.identifier = Mock(return_value="SAFE_IDENTIFIER")
                mock_sql.return_value = "SAFE_QUERY"

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
