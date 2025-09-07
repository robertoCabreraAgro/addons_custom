"""
Test handling of Odoo 18 Domain objects.

Odoo 18 introduces Domain objects (DomainAnd, DomainOr, etc.)
that need special handling in our geo operator processing.
"""

from unittest.mock import Mock, MagicMock
from odoo.tests import common


class TestDomainObjects(common.TransactionCase):
    """Test handling of Odoo 18's Domain objects with geo operators."""

    def test_domain_object_with_to_list(self):
        """Test processing of Domain objects that have to_list() method."""
        # Create a mock Domain object (like DomainAnd)
        mock_domain = Mock()
        mock_domain.to_list.return_value = [
            ("field1", "=", "value1"),
            ("location", "geo_within", "POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))"),
        ]

        # Mock the model
        MockModel = type(
            "MockModel",
            (self.env["base"].__class__,),
            {
                "_name": "test.geo.model",
                "_table": "test_geo_model",
                "_fields": {},
                "_GEO_OPERATORS": ["geo_within", "geo_contains", "geo_intersect"],
            },
        )

        mock_instance = MockModel()
        mock_instance.env = self.env

        # Mock _process_geo_operator to return IDs
        mock_instance._process_geo_operator = Mock(return_value={1, 2, 3})

        # Process the domain
        result = mock_instance._process_domain_with_geo(mock_domain)

        # Verify to_list was called
        mock_domain.to_list.assert_called_once()

        # Verify result is a list (not a Domain object)
        self.assertIsInstance(result, list)

        # Verify geo operator was converted
        self.assertIn(("field1", "=", "value1"), result)
        self.assertIn(("id", "in", [1, 2, 3]), result)

    def test_regular_list_domain(self):
        """Test that regular list domains still work."""
        domain = [("active", "=", True), ("location", "geo_intersect", "POINT(5 5)")]

        MockModel = type(
            "MockModel",
            (self.env["base"].__class__,),
            {
                "_name": "test.geo.model",
                "_table": "test_geo_model",
                "_fields": {},
                "_GEO_OPERATORS": ["geo_intersect"],
            },
        )

        mock_instance = MockModel()
        mock_instance.env = self.env
        mock_instance._process_geo_operator = Mock(return_value={4, 5, 6})

        # Process the domain
        result = mock_instance._process_domain_with_geo(domain)

        # Verify it's still a list
        self.assertIsInstance(result, list)

        # Verify content
        self.assertIn(("active", "=", True), result)
        self.assertIn(("id", "in", [4, 5, 6]), result)

    def test_empty_and_none_domains(self):
        """Test handling of empty and None domains."""
        MockModel = type(
            "MockModel",
            (self.env["base"].__class__,),
            {
                "_name": "test.geo.model",
                "_table": "test_geo_model",
                "_fields": {},
                "_GEO_OPERATORS": [],
            },
        )

        mock_instance = MockModel()

        # Test None domain
        result = mock_instance._process_domain_with_geo(None)
        self.assertIsNone(result)

        # Test empty list
        result = mock_instance._process_domain_with_geo([])
        self.assertEqual(result, [])

        # Test Domain object returning empty list
        mock_domain = Mock()
        mock_domain.to_list.return_value = []
        result = mock_instance._process_domain_with_geo(mock_domain)
        self.assertEqual(result, [])

    def test_complex_domain_object(self):
        """Test complex Domain object with nested conditions."""
        # Simulate a complex domain like:
        # DomainAnd([
        #     ('active', '=', True),
        #     DomainOr([
        #         ('location', 'geo_within', area1),
        #         ('location', 'geo_within', area2)
        #     ])
        # ])
        mock_domain = Mock()
        mock_domain.to_list.return_value = [
            "&",
            ("active", "=", True),
            "|",
            ("location", "geo_within", "POLYGON((0 0, 5 0, 5 5, 0 5, 0 0))"),
            ("location", "geo_within", "POLYGON((5 5, 10 5, 10 10, 5 10, 5 5))"),
        ]

        MockModel = type(
            "MockModel",
            (self.env["base"].__class__,),
            {
                "_name": "test.geo.model",
                "_table": "test_geo_model",
                "_fields": {},
                "_GEO_OPERATORS": ["geo_within"],
            },
        )

        mock_instance = MockModel()
        mock_instance.env = self.env

        # Mock different results for each geo operation
        call_count = 0

        def mock_process_geo(*args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {1, 2, 3}
            else:
                return {3, 4, 5}

        mock_instance._process_geo_operator = mock_process_geo

        # Process the domain
        result = mock_instance._process_domain_with_geo(mock_domain)

        # Verify structure is preserved
        self.assertEqual(result[0], "&")
        self.assertEqual(result[1], ("active", "=", True))
        self.assertEqual(result[2], "|")
        # Geo operators should be converted to ID conditions
        self.assertIn(("id", "in", [1, 2, 3]), result)
        self.assertIn(("id", "in", [3, 4, 5]), result)

    def test_unknown_domain_format(self):
        """Test that unknown domain formats are returned as-is."""
        # Create an object that's neither a list nor has to_list()
        unknown_domain = "some strange format"

        MockModel = type(
            "MockModel",
            (self.env["base"].__class__,),
            {
                "_name": "test.geo.model",
                "_table": "test_geo_model",
                "_fields": {},
                "_GEO_OPERATORS": [],
            },
        )

        mock_instance = MockModel()

        # Should return unchanged
        result = mock_instance._process_domain_with_geo(unknown_domain)
        self.assertEqual(result, unknown_domain)
