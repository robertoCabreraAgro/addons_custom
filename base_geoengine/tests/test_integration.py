#!/usr/bin/env python3
"""Integration test for search method with geo operators.

This test simulates the full search flow without requiring Odoo environment.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class MockCursor:
    """Mock database cursor."""

    def __init__(self):
        self.queries = []
        self.results = []

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchall(self):
        if self.results:
            return self.results.pop(0)
        return []


class MockEnv:
    """Mock Odoo environment."""

    def __init__(self):
        self.cr = MockCursor()


class MockGeoField:
    """Mock geo field."""

    def __init__(self, field_type="geo_point", srid=3857):
        self.type = field_type
        self.srid = srid
        self.dim = 2
        self.geo_type = field_type.replace("geo_", "").upper()


class MockSuperClass:
    """Mock parent class for search."""

    def __init__(self):
        self.search_calls = []
        self.search_count_calls = []
        self.search_read_calls = []

    def search(self, domain, offset=0, limit=None, order=None):
        self.search_calls.append(
            {"domain": domain, "offset": offset, "limit": limit, "order": order}
        )
        # Return mock recordset
        return MockRecordset([1, 2, 3])

    def search_count(self, domain):
        self.search_count_calls.append({"domain": domain})
        return 3

    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        self.search_read_calls.append(
            {
                "domain": domain,
                "fields": fields,
                "offset": offset,
                "limit": limit,
                "order": order,
            }
        )
        return [
            {"id": 1, "name": "Test 1"},
            {"id": 2, "name": "Test 2"},
            {"id": 3, "name": "Test 3"},
        ]


class MockRecordset:
    """Mock Odoo recordset."""

    def __init__(self, ids):
        self.ids = ids


class TestSearchIntegration:
    """Test model with full search implementation."""

    _GEO_OPERATORS = [
        "geo_greater",
        "geo_lesser",
        "geo_equal",
        "geo_touch",
        "geo_within",
        "geo_contains",
        "geo_intersect",
    ]

    def __init__(self):
        self._table = "test_model"
        self._fields = {
            "name": MockGeoField("char"),
            "active": MockGeoField("boolean"),
            "geo_point": MockGeoField("geo_point"),
            "geo_polygon": MockGeoField("geo_polygon"),
        }
        self.env = MockEnv()
        self._super = MockSuperClass()

    def _is_geo_term(self, term):
        """Check if a domain term is a geo operator."""
        return (
            isinstance(term, (list, tuple))
            and len(term) == 3
            and isinstance(term[1], str)
            and term[1] in self._GEO_OPERATORS
        )

    def _process_geo_operator(self, field_name, operator, value):
        """Simulate geo operator processing."""
        field = self._fields.get(field_name)
        if (
            not field
            or not isinstance(field, MockGeoField)
            or not field.type.startswith("geo_")
        ):
            return None

        # Simulate SQL execution
        self.env.cr.execute(
            f"SELECT id FROM {self._table} WHERE geo_condition", [value, field.srid]
        )

        # Return mock IDs
        if field_name == "geo_point" and operator == "geo_intersect":
            return {1, 2, 3, 4, 5}
        elif field_name == "geo_polygon" and operator == "geo_within":
            return {2, 3, 4, 6}
        else:
            return {1, 2, 3}

    def _process_domain_with_geo(self, domain):
        """Process domain by converting geo operators to ID conditions."""
        if not domain:
            return domain

        result = []
        i = 0

        while i < len(domain):
            term = domain[i]

            # Handle logical operators
            if term in ("&", "|"):
                result.append(term)
                i += 1
            elif term == "!":
                result.append(term)
                i += 1
                # Process next term (which is being negated)
                if i < len(domain):
                    next_term = domain[i]
                    if self._is_geo_term(next_term):
                        # Convert negated geo operator
                        ids = self._process_geo_operator(
                            next_term[0], next_term[1], next_term[2]
                        )
                        if ids is not None:
                            result.append(("id", "not in", list(ids)))
                        else:
                            result.append(next_term)
                    else:
                        result.append(next_term)
                    i += 1
            # Handle leaf conditions
            elif self._is_geo_term(term):
                # Convert geo operator to ID filter
                field_name, operator, value = term
                ids = self._process_geo_operator(field_name, operator, value)
                if ids is not None:
                    result.append(("id", "in", list(ids)))
                else:
                    result.append(term)
                i += 1
            else:
                # Regular condition, keep as-is
                result.append(term)
                i += 1

        return result

    def search(self, domain, offset=0, limit=None, order=None):
        """Search with geo operators support."""
        processed_domain = self._process_domain_with_geo(domain)
        return self._super.search(
            processed_domain, offset=offset, limit=limit, order=order
        )

    def search_count(self, domain):
        """Search count with geo operators support."""
        processed_domain = self._process_domain_with_geo(domain)
        return self._super.search_count(processed_domain)

    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """Search read with geo operators support."""
        if domain:
            domain = self._process_domain_with_geo(domain)
        return self._super.search_read(
            domain=domain, fields=fields, offset=offset, limit=limit, order=order
        )


def test_search_with_geo():
    """Test search method with geo operators."""
    model = TestSearchIntegration()

    # Test simple geo search
    result = model.search([("geo_point", "geo_intersect", "POINT(0 0)")])

    assert len(model._super.search_calls) == 1, "Expected one search call"
    call = model._super.search_calls[0]
    assert len(call["domain"]) == 1, "Expected one domain term"
    assert call["domain"][0][0] == "id", "Expected ID filter"
    assert call["domain"][0][1] == "in", "Expected 'in' operator"

    print("✓ Simple geo search test passed")


def test_search_with_mixed_domain():
    """Test search with mixed regular and geo operators."""
    model = TestSearchIntegration()

    result = model.search(
        [
            ("name", "=", "Test"),
            ("geo_point", "geo_intersect", "POINT(0 0)"),
            ("active", "=", True),
        ],
        offset=10,
        limit=20,
        order="name",
    )

    assert len(model._super.search_calls) == 1, "Expected one search call"
    call = model._super.search_calls[0]
    assert len(call["domain"]) == 3, "Expected three domain terms"
    assert call["domain"][0] == ("name", "=", "Test"), "First term should be unchanged"
    assert call["domain"][1][0] == "id", "Second term should be ID filter"
    assert call["domain"][2] == ("active", "=", True), "Third term should be unchanged"
    assert call["offset"] == 10, "Offset should be preserved"
    assert call["limit"] == 20, "Limit should be preserved"
    assert call["order"] == "name", "Order should be preserved"

    print("✓ Mixed domain search test passed")


def test_search_with_complex_domain():
    """Test search with complex domain including OR."""
    model = TestSearchIntegration()

    result = model.search(
        [
            "|",
            ("geo_point", "geo_intersect", "POINT(0 0)"),
            "&",
            ("name", "=", "Test"),
            ("geo_polygon", "geo_within", "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"),
        ]
    )

    assert len(model._super.search_calls) == 1, "Expected one search call"
    call = model._super.search_calls[0]
    assert call["domain"][0] == "|", "First element should be OR"
    assert call["domain"][1][0] == "id", "Second element should be ID filter"
    assert call["domain"][2] == "&", "Third element should be AND"
    assert call["domain"][3] == ("name", "=", "Test"), "Fourth element unchanged"
    assert call["domain"][4][0] == "id", "Fifth element should be ID filter"

    print("✓ Complex domain search test passed")


def test_search_count():
    """Test search_count with geo operators."""
    model = TestSearchIntegration()

    count = model.search_count([("geo_point", "geo_intersect", "POINT(0 0)")])

    assert count == 3, f"Expected count 3, got {count}"
    assert len(model._super.search_count_calls) == 1, "Expected one search_count call"
    call = model._super.search_count_calls[0]
    assert call["domain"][0][0] == "id", "Domain should have ID filter"

    print("✓ Search count test passed")


def test_search_read():
    """Test search_read with geo operators."""
    model = TestSearchIntegration()

    result = model.search_read(
        [("geo_point", "geo_intersect", "POINT(0 0)")],
        fields=["name"],
        offset=5,
        limit=10,
    )

    assert len(result) == 3, f"Expected 3 results, got {len(result)}"
    assert len(model._super.search_read_calls) == 1, "Expected one search_read call"
    call = model._super.search_read_calls[0]
    assert call["domain"][0][0] == "id", "Domain should have ID filter"
    assert call["fields"] == ["name"], "Fields should be preserved"
    assert call["offset"] == 5, "Offset should be preserved"
    assert call["limit"] == 10, "Limit should be preserved"

    print("✓ Search read test passed")


def test_negation():
    """Test search with NOT operator."""
    model = TestSearchIntegration()

    result = model.search(
        ["!", ("geo_point", "geo_within", "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))")]
    )

    assert len(model._super.search_calls) == 1, "Expected one search call"
    call = model._super.search_calls[0]
    assert call["domain"][0] == "!", "First element should be NOT"
    assert call["domain"][1][0] == "id", "Second element should be ID filter"
    assert call["domain"][1][1] == "not in", "Should use 'not in' for negation"

    print("✓ Negation test passed")


def test_sql_execution():
    """Test that SQL is executed for geo operators."""
    model = TestSearchIntegration()

    result = model.search([("geo_point", "geo_intersect", "POINT(0 0)")])

    # Check that SQL was executed
    assert len(model.env.cr.queries) > 0, "Expected SQL queries"
    query, params = model.env.cr.queries[0]
    assert params is not None, "Expected query parameters"
    assert len(params) == 2, f"Expected 2 parameters (value, srid), got {len(params)}"

    print("✓ SQL execution test passed")


def run_all_tests():
    """Run all integration tests."""
    print("Running integration tests for search method...")
    print("-" * 50)

    tests = [
        test_search_with_geo,
        test_search_with_mixed_domain,
        test_search_with_complex_domain,
        test_search_count,
        test_search_read,
        test_negation,
        test_sql_execution,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__} failed: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} error: {e}")
            failed += 1

    print("-" * 50)
    print(f"Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("✅ All integration tests passed successfully!")
        return 0
    else:
        print(f"❌ {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
