#!/usr/bin/env python3
"""Standalone test to verify search implementation logic.

This test can run without full Odoo environment to verify the core logic.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class MockField:
    """Mock field for testing."""

    def __init__(self, field_type="char"):
        self.type = field_type
        self.srid = 3857 if field_type.startswith("geo_") else None


class TestModel:
    """Test model with domain processing logic."""

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
        self._fields = {
            "name": MockField("char"),
            "active": MockField("boolean"),
            "geo_point": MockField("geo_point"),
            "geo_polygon": MockField("geo_polygon"),
        }
        self._geo_results = {}  # Store mock results for geo operators

    def _is_geo_term(self, term):
        """Check if a domain term is a geo operator."""
        return (
            isinstance(term, (list, tuple))
            and len(term) == 3
            and isinstance(term[1], str)
            and term[1] in self._GEO_OPERATORS
        )

    def _process_geo_operator(self, field_name, operator, value):
        """Mock geo operator processing."""
        field = self._fields.get(field_name)
        if not field or not field.type.startswith("geo_"):
            return None

        # Return mock IDs for testing
        key = (field_name, operator, value)
        if key in self._geo_results:
            return self._geo_results[key]

        # Default mock result
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
            if term == "&":
                result.append(term)
                i += 1
            elif term == "|":
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
                    # Not a valid geo field, keep original term
                    result.append(term)
                i += 1
            else:
                # Regular condition, keep as-is
                result.append(term)
                i += 1

        return result


def test_empty_domain():
    """Test empty domain processing."""
    model = TestModel()
    result = model._process_domain_with_geo([])
    assert result == [], f"Expected empty list, got {result}"
    print("✓ Empty domain test passed")


def test_regular_domain():
    """Test domain with only regular operators."""
    model = TestModel()
    domain = [
        ("name", "=", "Test"),
        ("active", "=", True),
    ]
    result = model._process_domain_with_geo(domain)
    assert result == domain, f"Expected {domain}, got {result}"
    print("✓ Regular domain test passed")


def test_simple_geo_domain():
    """Test domain with single geo operator."""
    model = TestModel()
    domain = [("geo_point", "geo_intersect", "POINT(0 0)")]
    result = model._process_domain_with_geo(domain)

    assert len(result) == 1, f"Expected 1 term, got {len(result)}"
    assert result[0][0] == "id", f"Expected 'id' field, got {result[0][0]}"
    assert result[0][1] == "in", f"Expected 'in' operator, got {result[0][1]}"
    assert set(result[0][2]) == {1, 2, 3}, f"Expected {{1,2,3}}, got {result[0][2]}"
    print("✓ Simple geo domain test passed")


def test_mixed_domain():
    """Test domain with mixed regular and geo operators."""
    model = TestModel()
    domain = [
        ("name", "=", "Test"),
        ("geo_point", "geo_within", "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"),
        ("active", "=", True),
    ]
    result = model._process_domain_with_geo(domain)

    assert len(result) == 3, f"Expected 3 terms, got {len(result)}"
    assert result[0] == ("name", "=", "Test"), f"First term incorrect: {result[0]}"
    assert result[1][0] == "id", f"Second term should be ID filter: {result[1]}"
    assert result[2] == ("active", "=", True), f"Third term incorrect: {result[2]}"
    print("✓ Mixed domain test passed")


def test_complex_domain_with_or():
    """Test complex domain with OR operator."""
    model = TestModel()
    domain = [
        "|",
        ("geo_point", "geo_intersect", "POINT(0 0)"),
        ("name", "=", "Test"),
    ]
    result = model._process_domain_with_geo(domain)

    assert len(result) == 3, f"Expected 3 terms, got {len(result)}"
    assert result[0] == "|", f"Expected OR operator, got {result[0]}"
    assert result[1][0] == "id", f"Expected ID filter, got {result[1]}"
    assert result[2] == ("name", "=", "Test"), f"Expected regular term, got {result[2]}"
    print("✓ Complex domain with OR test passed")


def test_complex_domain_with_and():
    """Test complex domain with AND operator."""
    model = TestModel()
    domain = [
        "&",
        ("active", "=", True),
        ("geo_polygon", "geo_contains", "POINT(1 1)"),
    ]
    result = model._process_domain_with_geo(domain)

    assert len(result) == 3, f"Expected 3 terms, got {len(result)}"
    assert result[0] == "&", f"Expected AND operator, got {result[0]}"
    assert result[1] == ("active", "=", True), f"Expected regular term, got {result[1]}"
    assert result[2][0] == "id", f"Expected ID filter, got {result[2]}"
    print("✓ Complex domain with AND test passed")


def test_negation():
    """Test domain with NOT operator."""
    model = TestModel()
    domain = [
        "!",
        ("geo_point", "geo_within", "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"),
    ]
    result = model._process_domain_with_geo(domain)

    assert len(result) == 2, f"Expected 2 terms, got {len(result)}"
    assert result[0] == "!", f"Expected NOT operator, got {result[0]}"
    assert result[1][0] == "id", f"Expected ID filter, got {result[1]}"
    assert result[1][1] == "not in", f"Expected 'not in' operator, got {result[1][1]}"
    print("✓ Negation test passed")


def test_nested_complex_domain():
    """Test nested complex domain."""
    model = TestModel()

    # Set specific results for different geo operators
    model._geo_results[("geo_point", "geo_intersect", "POINT(0 0)")] = {1, 2, 3}
    model._geo_results[
        ("geo_polygon", "geo_within", "POLYGON((0 0, 2 0, 2 2, 0 2, 0 0))")
    ] = {2, 3, 4}

    domain = [
        "|",
        "&",
        ("type", "=", "warehouse"),
        ("geo_point", "geo_intersect", "POINT(0 0)"),
        "&",
        ("type", "=", "store"),
        ("geo_polygon", "geo_within", "POLYGON((0 0, 2 0, 2 2, 0 2, 0 0))"),
    ]

    result = model._process_domain_with_geo(domain)

    assert len(result) == 7, f"Expected 7 terms, got {len(result)}: {result}"
    assert result[0] == "|", f"Expected OR at position 0"
    assert result[1] == "&", f"Expected AND at position 1"
    assert result[2] == (
        "type",
        "=",
        "warehouse",
    ), f"Expected type=warehouse at position 2"
    assert (
        result[3][0] == "id" and result[3][1] == "in"
    ), f"Expected ID filter at position 3"
    assert result[4] == "&", f"Expected AND at position 4"
    assert result[5] == ("type", "=", "store"), f"Expected type=store at position 5"
    assert (
        result[6][0] == "id" and result[6][1] == "in"
    ), f"Expected ID filter at position 6"
    print("✓ Nested complex domain test passed")


def test_invalid_geo_field():
    """Test geo operator on non-geo field."""
    model = TestModel()
    domain = [("name", "geo_intersect", "POINT(0 0)")]
    result = model._process_domain_with_geo(domain)

    # Should keep original term since 'name' is not a geo field
    assert result == domain, f"Expected original domain, got {result}"
    print("✓ Invalid geo field test passed")


def run_all_tests():
    """Run all tests."""
    print("Running standalone tests for domain processing...")
    print("-" * 50)

    tests = [
        test_empty_domain,
        test_regular_domain,
        test_simple_geo_domain,
        test_mixed_domain,
        test_complex_domain_with_or,
        test_complex_domain_with_and,
        test_negation,
        test_nested_complex_domain,
        test_invalid_geo_field,
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
        print("✅ All tests passed successfully!")
        return 0
    else:
        print(f"❌ {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
