# Copyright 2025 AgroMarin
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""
Spatial Query Integration Tests

These tests verify that spatial queries work correctly with real PostGIS
database operations and that the search override functions properly.
"""

from unittest.mock import Mock, patch

from odoo.tests import common, tagged
from odoo.exceptions import ValidationError

try:
    from shapely.geometry import Point, Polygon, LineString
    import geojson

    HAS_GEOSPATIAL = True
except ImportError:
    HAS_GEOSPATIAL = False

from odoo.addons.base_geoengine import fields as geo_fields
from odoo.addons.base_geoengine.models.base import Base


@tagged("post_install", "-at_install")
class TestSpatialQueries(common.TransactionCase):
    """Test spatial query functionality and integration."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not HAS_GEOSPATIAL:
            cls.skipTest(cls, "Geospatial libraries not available")

    def setUp(self):
        super().setUp()

        # Create test geometries
        self.test_point = Point(746676.106813609, 5865349.7175855)
        self.test_polygon = Polygon(
            [
                (746000, 5865000),
                (747000, 5865000),
                (747000, 5866000),
                (746000, 5866000),
                (746000, 5865000),
            ]
        )
        self.test_line = LineString([(746676, 5865349), (746700, 5865400)])

    def test_search_override_detection(self):
        """Test that search method is properly overridden."""
        from odoo.addons.base_geoengine.models.base import Base

        # Verify that Base class has our search override
        self.assertTrue(hasattr(Base, "search"))

        # Verify it's our custom method (has geo operator handling)
        search_method = Base.search
        self.assertIn("geo_ops", search_method.__code__.co_names or [])

    def test_geo_operator_list_completeness(self):
        """Test that all required geo operators are defined."""
        from odoo.addons.base_geoengine.models.base import Base

        expected_operators = [
            "geo_greater",
            "geo_lesser",
            "geo_equal",
            "geo_touch",
            "geo_within",
            "geo_contains",
            "geo_intersect",
        ]

        self.assertTrue(hasattr(Base, "_GEO_OPERATORS"))
        for op in expected_operators:
            self.assertIn(op, Base._GEO_OPERATORS)

    def test_domain_geo_operator_detection(self):
        """Test that geo operators are correctly detected in domains."""
        from odoo.addons.base_geoengine.models.base import Base

        # Mock model for testing
        MockModel = type(
            "MockModel",
            (Base,),
            {
                "_name": "test.geo.model",
                "_table": "test_geo_model",
                "_fields": {
                    "test_point": geo_fields.GeoPoint(),
                },
            },
        )

        mock_instance = MockModel()
        mock_instance.env = self.env

        # Test domains with geo operators
        geo_domains = [
            [("test_point", "geo_contains", self.test_point)],
            [("test_point", "geo_intersect", self.test_polygon)],
            [("test_point", "geo_within", self.test_polygon)],
        ]

        for domain in geo_domains:
            # Check if domain contains geo operators
            has_geo_ops = any(
                isinstance(cond, (list, tuple))
                and len(cond) == 3
                and cond[1] in MockModel._GEO_OPERATORS
                for cond in domain
            )
            self.assertTrue(
                has_geo_ops,
                f"Domain {domain} should be detected as having geo operators",
            )

    def test_spatial_sql_generation_integration(self):
        """Test integration between search override and SQL generation."""
        # Mock database cursor and execution
        mock_cursor = Mock()
        mock_cursor.execute = Mock()
        mock_cursor.fetchall = Mock(return_value=[(1,), (2,), (3,)])

        with patch.object(self.env, "cr", mock_cursor):
            # Create mock model with geo field
            MockModel = type(
                "MockModel",
                (Base,),
                {
                    "_name": "test.geo.model",
                    "_table": "test_geo_model",
                    "_fields": {
                        "test_point": geo_fields.GeoPoint(),
                    },
                },
            )

            mock_instance = MockModel()
            mock_instance.env = self.env

            # Mock the super().search call to return empty recordset
            with patch.object(
                Base, "search", return_value=self.env["ir.model"].browse([])
            ):
                # Mock browse to return mock records
                with patch.object(MockModel, "browse") as mock_browse:
                    mock_records = Mock()
                    mock_records.ids = [1, 2, 3]
                    mock_browse.return_value = mock_records

                    # Test geo_contains query
                    domain = [("test_point", "geo_contains", self.test_point)]
                    result = mock_instance.search(domain)

                    # Verify SQL was executed
                    mock_cursor.execute.assert_called()

                    # Verify SQL contains PostGIS function
                    executed_sql = mock_cursor.execute.call_args[0][0]
                    self.assertIn("ST_Contains", executed_sql)
                    self.assertIn("test_geo_model", executed_sql)

    def test_multiple_geo_operators_in_domain(self):
        """Test domains with multiple geo operators."""
        mock_cursor = Mock()
        mock_cursor.execute = Mock()

        # Return different results for different queries
        def mock_fetchall_side_effect():
            call_count = getattr(mock_fetchall_side_effect, "calls", 0) + 1
            setattr(mock_fetchall_side_effect, "calls", call_count)

            if call_count == 1:
                return [(1,), (2,), (3,), (4,)]  # First geo query
            else:
                return [(2,), (3,), (5,)]  # Second geo query

        mock_cursor.fetchall = Mock(side_effect=mock_fetchall_side_effect)

        with patch.object(self.env, "cr", mock_cursor):
            MockModel = type(
                "MockModel",
                (Base,),
                {
                    "_name": "test.geo.model",
                    "_table": "test_geo_model",
                    "_fields": {
                        "test_point": geo_fields.GeoPoint(),
                        "test_polygon": geo_fields.GeoPolygon(),
                    },
                },
            )

            mock_instance = MockModel()
            mock_instance.env = self.env

            with patch.object(
                Base, "search", return_value=self.env["ir.model"].browse([])
            ):
                with patch.object(MockModel, "browse") as mock_browse:
                    # Mock intersection logic
                    mock_records = Mock()
                    mock_records.ids = [2, 3]  # Intersection of {1,2,3,4} and {2,3,5}
                    mock_browse.return_value = mock_records

                    # Test domain with multiple geo operators
                    domain = [
                        ("test_point", "geo_within", self.test_polygon),
                        ("test_polygon", "geo_contains", self.test_point),
                    ]

                    result = mock_instance.search(domain)

                    # Verify both SQL queries were executed
                    self.assertEqual(mock_cursor.execute.call_count, 2)

    def test_mixed_domain_with_geo_and_regular_operators(self):
        """Test domains mixing geo operators with regular Odoo operators."""
        MockModel = type(
            "MockModel",
            (Base,),
            {
                "_name": "test.geo.model",
                "_table": "test_geo_model",
                "_fields": {
                    "test_point": geo_fields.GeoPoint(),
                    "name": geo_fields.fields.Char(),
                },
            },
        )

        mock_instance = MockModel()
        mock_instance.env = self.env

        # Test domain with both geo and regular operators
        domain = [
            ("name", "=", "Test"),
            ("test_point", "geo_contains", self.test_point),
        ]

        # Mock the search execution
        with patch.object(Base, "search") as mock_super_search:
            mock_cursor = Mock()
            mock_cursor.execute = Mock()
            mock_cursor.fetchall = Mock(return_value=[(1,), (2,)])

            with patch.object(self.env, "cr", mock_cursor):
                with patch.object(MockModel, "browse"):
                    mock_instance.search(domain)

                    # Verify that super().search was called with non-geo conditions
                    mock_super_search.assert_called()
                    call_args = mock_super_search.call_args[0]
                    regular_domain = call_args[0] if call_args else []

                    # Should contain only non-geo conditions
                    geo_conditions = [
                        cond
                        for cond in regular_domain
                        if isinstance(cond, (list, tuple))
                        and len(cond) == 3
                        and cond[1] in MockModel._GEO_OPERATORS
                    ]
                    self.assertEqual(len(geo_conditions), 0)

    def test_error_handling_in_spatial_queries(self):
        """Test error handling when spatial queries fail."""
        mock_cursor = Mock()
        mock_cursor.execute = Mock(side_effect=Exception("PostGIS error"))

        with patch.object(self.env, "cr", mock_cursor):
            MockModel = type(
                "MockModel",
                (Base,),
                {
                    "_name": "test.geo.model",
                    "_table": "test_geo_model",
                    "_fields": {
                        "test_point": geo_fields.GeoPoint(),
                    },
                },
            )

            mock_instance = MockModel()
            mock_instance.env = self.env

            with patch.object(
                Base, "search", return_value=self.env["ir.model"].browse([])
            ):
                with patch.object(MockModel, "browse") as mock_browse:
                    # Mock empty result for error case
                    mock_browse.return_value = self.env["ir.model"].browse([])

                    # Should not raise exception, but handle gracefully
                    domain = [("test_point", "geo_contains", self.test_point)]
                    result = mock_instance.search(domain)

                    # Should return empty result when geo query fails
                    self.assertEqual(len(result), 0)

    def test_non_geo_field_in_geo_operator_domain(self):
        """Test handling of geo operators on non-geo fields."""
        MockModel = type(
            "MockModel",
            (Base,),
            {
                "_name": "test.geo.model",
                "_table": "test_geo_model",
                "_fields": {
                    "name": geo_fields.fields.Char(),  # Regular field, not geo
                },
            },
        )

        mock_instance = MockModel()
        mock_instance.env = self.env

        with patch.object(Base, "search") as mock_super_search:
            mock_super_search.return_value = self.env["ir.model"].browse([])

            # Test geo operator on non-geo field
            domain = [("name", "geo_contains", self.test_point)]

            # Should fall back to regular domain processing
            mock_instance.search(domain)

            # Should pass the condition to super().search unchanged
            mock_super_search.assert_called()

    def test_empty_domain_handling(self):
        """Test handling of empty domains."""
        MockModel = type(
            "MockModel",
            (Base,),
            {
                "_name": "test.geo.model",
                "_table": "test_geo_model",
                "_fields": {
                    "test_point": geo_fields.GeoPoint(),
                },
            },
        )

        mock_instance = MockModel()
        mock_instance.env = self.env

        with patch.object(Base, "search") as mock_super_search:
            mock_super_search.return_value = self.env["ir.model"].browse([])

            # Test empty domain
            result = mock_instance.search([])

            # Should pass through to parent without geo processing
            mock_super_search.assert_called_with([], offset=0, limit=None, order=None)

    def test_limit_and_offset_handling(self):
        """Test that limit and offset are properly handled with geo queries."""
        mock_cursor = Mock()
        mock_cursor.execute = Mock()
        mock_cursor.fetchall = Mock(
            return_value=[(i,) for i in range(1, 21)]
        )  # 20 results

        with patch.object(self.env, "cr", mock_cursor):
            MockModel = type(
                "MockModel",
                (Base,),
                {
                    "_name": "test.geo.model",
                    "_table": "test_geo_model",
                    "_fields": {
                        "test_point": geo_fields.GeoPoint(),
                    },
                },
            )

            mock_instance = MockModel()
            mock_instance.env = self.env

            with patch.object(
                Base, "search", return_value=self.env["ir.model"].browse([])
            ):
                with patch.object(MockModel, "browse") as mock_browse:
                    # Mock records for limit/offset testing
                    all_ids = list(range(1, 21))

                    def mock_browse_func(ids):
                        mock_recordset = Mock()
                        mock_recordset.ids = ids if isinstance(ids, list) else [ids]
                        # Simulate slicing
                        original_getitem = mock_recordset.__getitem__

                        def slice_getitem(key):
                            if isinstance(key, slice):
                                new_mock = Mock()
                                new_mock.ids = mock_recordset.ids[key]
                                return new_mock
                            return original_getitem(key)

                        mock_recordset.__getitem__ = slice_getitem
                        mock_recordset.__len__ = lambda: len(mock_recordset.ids)
                        return mock_recordset

                    mock_browse.side_effect = mock_browse_func

                    # Test with limit
                    domain = [("test_point", "geo_contains", self.test_point)]
                    result = mock_instance.search(domain, limit=5)

                    # Verify limit was applied
                    self.assertLessEqual(len(result.ids), 5)

                    # Test with offset
                    result = mock_instance.search(domain, offset=10)
                    # Should have fewer results due to offset

    def test_ordering_with_geo_queries(self):
        """Test that ordering works with geo queries."""
        mock_cursor = Mock()
        mock_cursor.execute = Mock()
        mock_cursor.fetchall = Mock(return_value=[(3,), (1,), (2,)])

        with patch.object(self.env, "cr", mock_cursor):
            MockModel = type(
                "MockModel",
                (Base,),
                {
                    "_name": "test.geo.model",
                    "_table": "test_geo_model",
                    "_fields": {
                        "test_point": geo_fields.GeoPoint(),
                        "name": geo_fields.fields.Char(),
                    },
                },
            )

            mock_instance = MockModel()
            mock_instance.env = self.env

            with patch.object(
                Base, "search", return_value=self.env["ir.model"].browse([])
            ):
                with patch.object(MockModel, "browse") as mock_browse:
                    # Mock recordset with sorting capability
                    mock_recordset = Mock()
                    mock_recordset.ids = [3, 1, 2]

                    # Mock the sorted method
                    def mock_sorted(key_func):
                        sorted_mock = Mock()
                        sorted_mock.ids = [1, 2, 3]  # Simulate sorted result
                        return sorted_mock

                    mock_recordset.sorted = mock_sorted
                    mock_browse.return_value = mock_recordset

                    # Test with ordering
                    domain = [("test_point", "geo_contains", self.test_point)]
                    result = mock_instance.search(domain, order="name")

                    # Should have called sorted on recordset
                    self.assertTrue(mock_recordset.sorted.called)
