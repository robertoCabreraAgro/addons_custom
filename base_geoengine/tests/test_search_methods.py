"""
Test search method overrides for Odoo 18 compatibility.

This test suite verifies that all search-related methods correctly handle:
1. Geo operators in domains
2. New Odoo 18 parameters (limit in search_count, count_limit in web_search_read)
3. Proper delegation to parent methods
"""

from unittest.mock import Mock, patch, MagicMock
from odoo.tests import common


class TestSearchMethods(common.TransactionCase):
    """Test all search method overrides for geo operators and Odoo 18 compatibility."""

    def setUp(self):
        super().setUp()
        # Create a mock model with geo fields
        self.MockModel = type(
            "MockModel",
            (self.env["base"].__class__,),
            {
                "_name": "test.geo.model",
                "_table": "test_geo_model",
                "_fields": {},
                "_GEO_OPERATORS": [
                    "geo_greater",
                    "geo_lesser",
                    "geo_equal",
                    "geo_touch",
                    "geo_within",
                    "geo_contains",
                    "geo_intersect",
                ],
            },
        )

    def test_search_with_geo_operators(self):
        """Test that search() correctly processes geo operators."""
        mock_instance = self.MockModel()
        mock_instance.env = self.env

        # Mock the _process_domain_with_geo to verify it's called
        with patch.object(mock_instance, "_process_domain_with_geo") as mock_process:
            mock_process.return_value = [("id", "in", [1, 2, 3])]

            # Mock super().search
            with patch.object(
                self.env["base"].__class__, "search"
            ) as mock_super_search:
                mock_super_search.return_value = self.env["base"].browse([])

                # Test with geo operator
                domain = [
                    ("location", "geo_within", "POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))")
                ]
                mock_instance.search(domain, offset=10, limit=20, order="id")

                # Verify domain was processed
                mock_process.assert_called_once_with(domain)
                # Verify super was called with processed domain
                mock_super_search.assert_called_once_with(
                    [("id", "in", [1, 2, 3])], offset=10, limit=20, order="id"
                )

    def test_search_count_with_limit(self):
        """Test that search_count() accepts limit parameter (Odoo 18 compatibility)."""
        mock_instance = self.MockModel()
        mock_instance.env = self.env

        with patch.object(mock_instance, "_process_domain_with_geo") as mock_process:
            mock_process.return_value = [("id", "in", [1, 2, 3])]

            with patch.object(self.env["base"].__class__, "search_count") as mock_super:
                mock_super.return_value = 3

                # Test with limit parameter (new in Odoo 18)
                domain = [("location", "geo_intersect", "POINT(5 5)")]
                result = mock_instance.search_count(domain, limit=100)

                # Verify limit is passed to super
                mock_super.assert_called_once_with([("id", "in", [1, 2, 3])], limit=100)
                self.assertEqual(result, 3)

    def test_search_read_with_geo_operators(self):
        """Test that search_read() processes geo operators."""
        mock_instance = self.MockModel()
        mock_instance.env = self.env

        with patch.object(mock_instance, "_process_domain_with_geo") as mock_process:
            mock_process.return_value = [("id", "in", [4, 5, 6])]

            with patch.object(self.env["base"].__class__, "search_read") as mock_super:
                mock_super.return_value = [
                    {"id": 4, "name": "Test 1"},
                    {"id": 5, "name": "Test 2"},
                ]

                # Test search_read
                domain = [("area", "geo_greater", 100)]
                result = mock_instance.search_read(
                    domain=domain, fields=["name"], offset=0, limit=10, order="name"
                )

                # Verify processing
                mock_process.assert_called_once_with(domain)
                mock_super.assert_called_once_with(
                    domain=[("id", "in", [4, 5, 6])],
                    fields=["name"],
                    offset=0,
                    limit=10,
                    order="name",
                )
                self.assertEqual(len(result), 2)

    def test_web_search_read_odoo18_compatibility(self):
        """Test that web_search_read() works with Odoo 18 parameters."""
        mock_instance = self.MockModel()
        mock_instance.env = self.env

        with patch.object(mock_instance, "_process_domain_with_geo") as mock_process:
            mock_process.return_value = [("id", "in", [7, 8, 9])]

            with patch.object(
                self.env["base"].__class__, "web_search_read"
            ) as mock_super:
                mock_super.return_value = {
                    "records": [{"id": 7}, {"id": 8}],
                    "count": 2,
                }

                # Test with all Odoo 18 parameters
                domain = [("location", "geo_contains", "POINT(3 3)")]
                specification = {"name": {}, "location": {}}

                result = mock_instance.web_search_read(
                    domain=domain,
                    specification=specification,
                    offset=0,
                    limit=50,
                    order="id desc",
                    count_limit=1000,  # New in Odoo 18
                )

                # Verify all parameters are passed correctly
                mock_process.assert_called_once_with(domain)
                mock_super.assert_called_once_with(
                    domain=[("id", "in", [7, 8, 9])],
                    specification=specification,
                    offset=0,
                    limit=50,
                    order="id desc",
                    count_limit=1000,
                )
                self.assertEqual(result["count"], 2)

    def test_empty_domain_handling(self):
        """Test that empty/None domains are handled correctly."""
        mock_instance = self.MockModel()
        mock_instance.env = self.env

        # Test search with None domain
        with patch.object(self.env["base"].__class__, "search") as mock_super:
            mock_super.return_value = self.env["base"].browse([])
            mock_instance.search(None)
            mock_super.assert_called_once_with(None, offset=0, limit=None, order=None)

        # Test search_read with empty domain
        with patch.object(self.env["base"].__class__, "search_read") as mock_super:
            mock_super.return_value = []
            mock_instance.search_read(domain=[])
            mock_super.assert_called_once_with(
                domain=[], fields=None, offset=0, limit=None, order=None
            )

    def test_method_signatures(self):
        """Verify all methods have correct signatures for Odoo 18."""
        from inspect import signature

        mock_instance = self.MockModel()

        # Check search signature
        search_sig = signature(mock_instance.search)
        self.assertIn("domain", search_sig.parameters)
        self.assertIn("offset", search_sig.parameters)
        self.assertIn("limit", search_sig.parameters)
        self.assertIn("order", search_sig.parameters)

        # Check search_count signature (must have limit for Odoo 18)
        search_count_sig = signature(mock_instance.search_count)
        self.assertIn("domain", search_count_sig.parameters)
        self.assertIn("limit", search_count_sig.parameters)

        # Check search_read signature
        search_read_sig = signature(mock_instance.search_read)
        self.assertIn("domain", search_read_sig.parameters)
        self.assertIn("fields", search_read_sig.parameters)
        self.assertIn("offset", search_read_sig.parameters)
        self.assertIn("limit", search_read_sig.parameters)
        self.assertIn("order", search_read_sig.parameters)

        # Check web_search_read signature (Odoo 18 specific)
        web_search_read_sig = signature(mock_instance.web_search_read)
        self.assertIn("domain", web_search_read_sig.parameters)
        self.assertIn("specification", web_search_read_sig.parameters)
        self.assertIn("offset", web_search_read_sig.parameters)
        self.assertIn("limit", web_search_read_sig.parameters)
        self.assertIn("order", web_search_read_sig.parameters)
        self.assertIn("count_limit", web_search_read_sig.parameters)
