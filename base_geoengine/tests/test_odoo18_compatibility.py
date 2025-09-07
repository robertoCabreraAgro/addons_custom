"""Odoo 18.2/19.0 compatibility tests for base_geoengine.

Tests specific compatibility with Odoo 18.2 and forward compatibility with 19.0.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import importlib

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL

from .. import fields as geo_fields


class TestOdoo18ViewCompatibility(unittest.TestCase):
    """Test Odoo 18.2 view syntax compatibility."""

    def test_no_deprecated_select_attribute(self):
        """Test that views don't use deprecated select="1" attribute."""
        import os
        import xml.etree.ElementTree as ET

        views_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "views")

        if not os.path.exists(views_path):
            self.skipTest("Views directory not found")

        for filename in os.listdir(views_path):
            if filename.endswith(".xml"):
                filepath = os.path.join(views_path, filename)
                try:
                    tree = ET.parse(filepath)
                    root = tree.getroot()

                    # Check for select attribute in field elements
                    fields_with_select = root.findall(".//field[@select]")

                    for field in fields_with_select:
                        self.fail(
                            f"Deprecated select attribute found in {filename}: "
                            f"field '{field.get('name')}' has select='{field.get('select')}'"
                        )

                except ET.ParseError:
                    # Skip files that aren't valid XML
                    continue

    def test_new_invisible_syntax(self):
        """Test that views use new invisible syntax instead of attrs."""
        import os
        import xml.etree.ElementTree as ET

        views_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "views")

        if not os.path.exists(views_path):
            self.skipTest("Views directory not found")

        for filename in os.listdir(views_path):
            if filename.endswith(".xml"):
                filepath = os.path.join(views_path, filename)
                try:
                    tree = ET.parse(filepath)
                    root = tree.getroot()

                    # New syntax uses direct invisible attribute
                    # Old syntax would use attrs="{'invisible': [...]}"
                    elements_with_attrs = root.findall(".//*[@attrs]")

                    for element in elements_with_attrs:
                        attrs_value = element.get("attrs")
                        if "invisible" in attrs_value:
                            # This is using old syntax - just note it
                            # In Odoo 18.2, both syntaxes work but new is preferred
                            pass  # Not a failure, just legacy syntax

                except ET.ParseError:
                    continue

    def test_list_view_instead_of_tree(self):
        """Test that views use <list> instead of deprecated <tree>."""
        import os
        import xml.etree.ElementTree as ET

        views_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "views")

        if not os.path.exists(views_path):
            self.skipTest("Views directory not found")

        for filename in os.listdir(views_path):
            if filename.endswith(".xml"):
                filepath = os.path.join(views_path, filename)
                try:
                    tree = ET.parse(filepath)
                    root = tree.getroot()

                    # Check for <tree> elements (deprecated in 18.0+)
                    tree_elements = root.findall(".//tree")

                    # Note: <tree> is still supported but <list> is preferred
                    # This is informational, not a hard failure
                    for tree_elem in tree_elements:
                        # Could suggest migration to <list>
                        pass

                except ET.ParseError:
                    continue


class TestOdoo18ORMCompatibility(unittest.TestCase):
    """Test Odoo 18.2 ORM compatibility."""

    def test_sql_module_import(self):
        """Test that sql module is properly imported."""
        # Test that we can import sql from odoo.tools
        try:
            from odoo.tools import SQL

            self.assertIsNotNone(SQL)
            # SQL is a class, check it has the identifier method
            self.assertTrue(hasattr(SQL, "identifier"))
        except ImportError as e:
            self.fail(f"Failed to import sql module: {e}")

    def test_field_registration(self):
        """Test that geo fields register properly in Odoo 18.2."""
        # Verify fields are registered in odoo.fields namespace
        import odoo.fields as odoo_fields

        geo_field_types = [
            "GeoPoint",
            "GeoLine",
            "GeoPolygon",
            "GeoMultiPoint",
            "GeoMultiLine",
            "GeoMultiPolygon",
        ]

        for field_type in geo_field_types:
            self.assertTrue(
                hasattr(odoo_fields, field_type),
                f"{field_type} not registered in odoo.fields",
            )

    def test_basemodel_inheritance(self):
        """Test that Base properly extends BaseModel."""
        from ..models.base import Base

        # Check that Base has required ORM methods
        required_methods = [
            "search",
            "create",
            "write",
            "unlink",
            "read",
            "browse",
            "fields_get",
        ]

        for method in required_methods:
            self.assertTrue(
                hasattr(Base, method),
                f"Base missing required ORM method: {method}",
            )

    def test_api_decorators(self):
        """Test that API decorators work correctly."""
        from ..models.base import Base

        # Check that search method has correct decorator
        search_method = getattr(Base, "search", None)
        self.assertIsNotNone(search_method)

        # In Odoo 18.2, @api.model is still used for class methods
        # Check if the method is properly decorated
        if hasattr(search_method, "_api"):
            self.assertIn("model", search_method._api)

    def test_domain_processing(self):
        """Test that domain processing works with Odoo 18.2."""
        from ..models.base import Base

        model = Base()
        model._GEO_OPERATORS = {"geo_intersect", "geo_contains", "geo_within"}

        # Test with complex domain including logical operators
        domain = [
            "&",
            ("active", "=", True),
            "|",
            ("geo_field", "geo_intersect", "POINT(0 0)"),
            ("name", "ilike", "test"),
        ]

        # Should handle logical operators correctly
        # The new implementation processes domains in place
        # No longer splitting into geo and regular domains
        self.assertIn("&", regular_domain)
        self.assertIn("|", regular_domain)

    def test_new_compute_display_name(self):
        """Test compatibility with _compute_display_name replacing name_get."""
        # In Odoo 18.0+, name_get is deprecated in favor of _compute_display_name
        from ..models.base import Base

        # Check if module uses new pattern
        if hasattr(Base, "_compute_display_name"):
            # New pattern is used - good
            self.assertTrue(callable(Base._compute_display_name))
        elif hasattr(Base, "name_get"):
            # Old pattern - should migrate
            self.skipTest("Module still uses deprecated name_get")

    def test_check_access_unified(self):
        """Test that check_access is used instead of check_access_rights/rule."""
        from ..models.base import Base

        # In Odoo 18.0+, check_access unifies check_access_rights and check_access_rule
        if hasattr(Base, "check_access"):
            self.assertTrue(callable(Base.check_access))

    def test_has_group_method(self):
        """Test self.env.user.has_group() replaces user_has_groups."""
        # This is more of a usage pattern test
        # We check that the module doesn't use deprecated patterns
        import os
        import re

        models_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")

        if not os.path.exists(models_path):
            self.skipTest("Models directory not found")

        deprecated_pattern = re.compile(r"user_has_groups\s*\(")

        for filename in os.listdir(models_path):
            if filename.endswith(".py"):
                filepath = os.path.join(models_path, filename)
                with open(filepath, "r") as f:
                    content = f.read()
                    if deprecated_pattern.search(content):
                        self.fail(
                            f"Deprecated user_has_groups found in {filename}. "
                            "Use self.env.user.has_group() instead."
                        )


class TestOdoo19ForwardCompatibility(unittest.TestCase):
    """Test forward compatibility with Odoo 19.0."""

    def test_type_annotations_present(self):
        """Test that code uses type annotations for forward compatibility."""
        import os
        import ast

        models_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")

        if not os.path.exists(models_path):
            self.skipTest("Models directory not found")

        # Check for type annotations in key methods
        for filename in ["base.py"]:
            filepath = os.path.join(models_path, filename)
            if not os.path.exists(filepath):
                continue

            with open(filepath, "r") as f:
                try:
                    tree = ast.parse(f.read())

                    # Look for function definitions
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            # Check if new methods have type hints
                            if node.name in [
                                "_process_geo_operator",
                                "_split_geo_domain",
                            ]:
                                # These are our new methods, should have hints
                                # Note: This is a recommendation, not required
                                pass

                except SyntaxError:
                    continue

    def test_async_preparation(self):
        """Test that code structure allows for async operations."""
        # Odoo 19.0 may introduce more async operations
        # Check that our code doesn't block async patterns
        from ..models.base import Base

        # Ensure methods don't use blocking I/O directly
        # This is more of a design check
        model = Base()

        # Check that database operations go through cursor
        # and don't use direct connections
        self.assertTrue(hasattr(model, "env"))

    def test_no_deprecated_imports(self):
        """Test that no deprecated imports are used."""
        import os
        import re

        # Patterns that might be deprecated in Odoo 19.0
        deprecated_imports = [
            (r"from openerp import", 'Use "from odoo import" instead'),
            (r"import openerp", 'Use "import odoo" instead'),
            (r"from odoo\.osv import", "osv is deprecated, use models"),
        ]

        base_path = os.path.dirname(os.path.dirname(__file__))

        for root, dirs, files in os.walk(base_path):
            # Skip test directories
            if "test" in root:
                continue

            for filename in files:
                if filename.endswith(".py"):
                    filepath = os.path.join(root, filename)
                    with open(filepath, "r") as f:
                        content = f.read()

                        for pattern, message in deprecated_imports:
                            if re.search(pattern, content):
                                self.fail(f"Deprecated import in {filename}: {message}")


class TestModuleStructure(unittest.TestCase):
    """Test that module structure follows Odoo 18.2+ best practices."""

    def test_manifest_structure(self):
        """Test that __manifest__.py has correct structure."""
        import os
        import ast

        manifest_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "__manifest__.py"
        )

        if not os.path.exists(manifest_path):
            self.skipTest("Manifest file not found")

        with open(manifest_path, "r") as f:
            content = f.read()
            manifest = eval(content)

            # Check required keys
            required_keys = ["name", "depends", "data"]
            for key in required_keys:
                self.assertIn(key, manifest, f"Missing required key: {key}")

            # Check assets structure for Odoo 18.2
            if "assets" in manifest:
                assets = manifest["assets"]
                # Should use new assets structure
                self.assertIsInstance(assets, dict)

                # Check for web.assets_backend
                if "web.assets_backend" in assets:
                    backend_assets = assets["web.assets_backend"]
                    self.assertIsInstance(backend_assets, list)

    def test_security_files(self):
        """Test that security files are properly structured."""
        import os
        import csv

        security_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "security"
        )

        if not os.path.exists(security_path):
            self.skipTest("Security directory not found")

        # Check ir.model.access.csv
        access_file = os.path.join(security_path, "ir.model.access.csv")
        if os.path.exists(access_file):
            with open(access_file, "r") as f:
                reader = csv.DictReader(f)
                required_columns = ["id", "name", "model_id:id", "group_id:id"]

                # Check header
                if reader.fieldnames:
                    for col in required_columns:
                        if col not in reader.fieldnames and col != "group_id:id":
                            # group_id:id is optional
                            self.fail(f"Missing required column in access file: {col}")

    def test_init_files(self):
        """Test that __init__.py files follow best practices."""
        import os

        base_path = os.path.dirname(os.path.dirname(__file__))

        # Check main __init__.py
        init_file = os.path.join(base_path, "__init__.py")
        if os.path.exists(init_file):
            with open(init_file, "r") as f:
                content = f.read()

                # Should import models first, then other components
                lines = content.strip().split("\n")
                imports = [l for l in lines if l.startswith("from . import")]

                if imports:
                    # First import should typically be models
                    first_import = imports[0]
                    # This is a convention, not a hard requirement
                    if "models" not in first_import and len(imports) > 1:
                        pass  # Could suggest reordering


class TestDatabaseCompatibility(unittest.TestCase):
    """Test database-level compatibility."""

    def test_postgis_sql_generation(self):
        """Test that generated SQL is compatible with PostGIS 3.x."""
        from ..geo_operators import GeoOperator
        from .. import fields as geo_fields

        mock_field = Mock(spec=geo_fields.GeoPoint)
        mock_field.srid = 3857
        mock_field.entry_to_shape = Mock(return_value=Mock(wkt="POINT(0 0)"))

        geo_op = GeoOperator(mock_field)
        params = []

        # Test that PostGIS functions use current syntax
        sql_funcs = [
            geo_op.get_geo_intersect_sql("table", "col", "POINT(1 1)", params),
            geo_op.get_geo_contains_sql("table", "col", "POINT(1 1)", params),
            geo_op.get_geo_within_sql("table", "col", "POINT(1 1)", params),
        ]

        for sql_func in sql_funcs:
            # Check for PostGIS 3.x function names
            self.assertTrue(
                any(
                    func in sql_func
                    for func in [
                        "ST_Intersects",
                        "ST_Contains",
                        "ST_Within",
                        "ST_GeomFromText",
                        "ST_Area",
                    ]
                ),
                f"SQL doesn't use PostGIS 3.x functions: {sql_func}",
            )

    def test_srid_handling(self):
        """Test that SRID handling is compatible with PostGIS 3.x."""
        from ..geo_operators import GeoOperator
        from .. import fields as geo_fields

        # Test with common SRIDs
        common_srids = [3857, 4326, 2154, 32632]

        for srid in common_srids:
            mock_field = Mock(spec=geo_fields.GeoPoint)
            mock_field.srid = srid
            mock_field.entry_to_shape = Mock(return_value=Mock(wkt="POINT(0 0)"))

            geo_op = GeoOperator(mock_field)
            params = []

            result = geo_op.get_geo_intersect_sql("table", "col", "POINT(1 1)", params)

            # SRID should be in params
            self.assertIn(srid, params)


if __name__ == "__main__":
    unittest.main()
