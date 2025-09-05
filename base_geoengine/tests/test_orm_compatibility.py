# Copyright 2025 AgroMarin
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""
ORM Compatibility Tests for base_geoengine

These tests are designed to detect changes in Odoo's ORM that might break
the base_geoengine module. They test the specific ORM interfaces and
behaviors that the module depends on.
"""

import inspect
from unittest.mock import Mock, patch

from odoo import fields, models
from odoo.orm import BaseModel
from odoo.tests import common, tagged
from odoo.exceptions import ValidationError

try:
    from shapely.geometry import Point, Polygon

    HAS_GEOSPATIAL = True
except ImportError:
    HAS_GEOSPATIAL = False

from odoo.addons.base_geoengine import fields as geo_fields
from odoo.addons.base_geoengine.models.base import Base


@tagged("post_install", "-at_install")
class TestORMCompatibility(common.TransactionCase):
    """Test ORM compatibility and interface stability."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not HAS_GEOSPATIAL:
            cls.skipTest(cls, "Geospatial libraries not available")

    def test_base_model_inheritance_structure(self):
        """Test that BaseModel inheritance structure hasn't changed."""
        # These are the ORM classes our module depends on
        self.assertTrue(hasattr(models, "BaseModel"))
        self.assertTrue(hasattr(models, "Model"))
        self.assertTrue(hasattr(models, "AbstractModel"))

        # Test that Base class properly inherits from AbstractModel
        from odoo.addons.base_geoengine.models.base import Base

        self.assertTrue(issubclass(Base, models.AbstractModel))

        # Test inheritance chain
        mro = Base.__mro__
        class_names = [cls.__name__ for cls in mro]
        self.assertIn("AbstractModel", class_names)
        self.assertIn("BaseModel", class_names)

    def test_search_method_signature(self):
        """Test that the search method signature hasn't changed."""
        # Get the current search method signature
        search_method = BaseModel.search
        sig = inspect.signature(search_method)

        # These parameters are critical for our search override
        expected_params = ["self", "domain", "offset", "limit", "order"]
        actual_params = list(sig.parameters.keys())

        for param in expected_params:
            self.assertIn(
                param,
                actual_params,
                f"Search method missing expected parameter: {param}",
            )

        # Test default values match expectations
        self.assertEqual(sig.parameters["offset"].default, 0)
        self.assertIsNone(sig.parameters["limit"].default)
        self.assertIsNone(sig.parameters["order"].default)

    def test_fields_get_method_compatibility(self):
        """Test that fields_get method interface is stable."""
        # Test that fields_get exists and has expected signature
        self.assertTrue(hasattr(BaseModel, "fields_get"))

        fields_get_method = BaseModel.fields_get
        sig = inspect.signature(fields_get_method)

        # Check expected parameters
        expected_params = ["self", "allfields", "attributes"]
        actual_params = list(sig.parameters.keys())

        for param in expected_params:
            self.assertIn(
                param,
                actual_params,
                f"fields_get method missing expected parameter: {param}",
            )

    def test_field_type_registration_mechanism(self):
        """Test that Odoo's field type registration mechanism still works."""
        from odoo import fields

        # Test that we can still register new field types
        original_geopoint = getattr(fields, "GeoPoint", None)

        # Verify our geo fields are registered
        self.assertTrue(hasattr(fields, "GeoPoint"))
        self.assertTrue(hasattr(fields, "GeoPolygon"))

        # Test that registered fields are proper Field subclasses
        self.assertTrue(issubclass(fields.GeoPoint, fields.Field))
        self.assertTrue(issubclass(fields.GeoPolygon, fields.Field))

    def test_domain_processing_compatibility(self):
        """Test that domain processing still works as expected."""
        # Create a test model that uses our Base mixin
        TestModel = type(
            "TestGeoModel",
            (Base, models.Model),
            {
                "_name": "test.geo.compatibility",
                "_description": "Test Geo Compatibility Model",
                "test_point": geo_fields.GeoPoint(),
            },
        )

        # Test that the model has the search method override
        self.assertTrue(hasattr(TestModel, "search"))

        # Test that our geo operators list is accessible
        self.assertTrue(hasattr(TestModel, "_GEO_OPERATORS"))
        self.assertIsInstance(TestModel._GEO_OPERATORS, list)
        self.assertIn("geo_contains", TestModel._GEO_OPERATORS)

    def test_model_creation_and_field_setup(self):
        """Test that model creation and field setup works."""
        # Test field attribute access patterns that our module uses
        mock_model = Mock()
        mock_model._fields = {
            "test_point": geo_fields.GeoPoint(),
        }

        # Test the field access pattern used in our search override
        field = mock_model._fields.get("test_point")
        self.assertIsInstance(field, geo_fields.GeoField)

        # Test table name access
        mock_model._table = "test_table"
        self.assertEqual(mock_model._table, "test_table")

    def test_env_and_cr_access_patterns(self):
        """Test that environment and cursor access patterns are stable."""
        # Test the env.cr access pattern used in our spatial queries
        model_instance = self.env["ir.model"]  # Use any existing model

        # These attributes are used in our geo operators
        self.assertTrue(hasattr(model_instance, "env"))
        self.assertTrue(hasattr(model_instance.env, "cr"))
        self.assertTrue(hasattr(model_instance.env.cr, "execute"))
        self.assertTrue(hasattr(model_instance.env.cr, "fetchall"))

    def test_recordset_operations_compatibility(self):
        """Test that recordset operations we depend on still work."""
        # Test with a simple model
        model = self.env["ir.model.fields"]

        # Test browse operation (used in our search results)
        if model.search([], limit=1):
            first_record = model.search([], limit=1)
            browsed = model.browse(first_record.id)
            self.assertEqual(browsed.id, first_record.id)

        # Test ids access (used in our search result processing)
        records = model.search([], limit=5)
        self.assertTrue(hasattr(records, "ids"))
        self.assertIsInstance(records.ids, list)

    def test_sql_execution_interface(self):
        """Test that SQL execution interface is stable."""
        cr = self.env.cr

        # Test execute method with parameters (used in our spatial queries)
        cr.execute("SELECT 1 as test WHERE %s = %s", (1, 1))
        result = cr.fetchone()
        self.assertEqual(result[0], 1)

        # Test fetchall method (used in our spatial query results)
        cr.execute("SELECT generate_series(1,3) as num")
        results = cr.fetchall()
        self.assertEqual(len(results), 3)

    def test_api_decorators_compatibility(self):
        """Test that API decorators we use are still available."""
        from odoo import api

        # Test decorators used in our code
        self.assertTrue(hasattr(api, "model"))
        self.assertTrue(hasattr(api, "depends"))
        self.assertTrue(hasattr(api, "constrains"))

        # Test that decorators can still be applied
        @api.model
        def test_model_method(self):
            pass

        # Test that the decorator worked
        self.assertTrue(hasattr(test_model_method, "_api"))

    def test_exception_classes_availability(self):
        """Test that exception classes we use are still available."""
        from odoo.exceptions import ValidationError, UserError, MissingError

        # Test that we can import and raise the exceptions we use
        with self.assertRaises(ValidationError):
            raise ValidationError("Test validation error")

        with self.assertRaises(UserError):
            raise UserError("Test user error")

        with self.assertRaises(MissingError):
            raise MissingError("Test missing error")

    def test_field_properties_interface(self):
        """Test that field properties interface is stable."""
        point_field = geo_fields.GeoPoint()

        # Test properties that our Base.fields_get override depends on
        self.assertTrue(hasattr(point_field, "type"))
        self.assertTrue(hasattr(point_field, "dim"))
        self.assertTrue(hasattr(point_field, "srid"))
        self.assertTrue(hasattr(point_field, "geo_type"))

        # Test that field type starts with 'geo_' as expected by fields_get
        self.assertTrue(point_field.type.startswith("geo_"))

    def test_model_registry_compatibility(self):
        """Test that model registry operations still work."""
        # Test registry access patterns used during module loading
        registry = self.env.registry

        # Test that we can access models from registry
        self.assertIn("ir.model", registry)

        # Test model loading patterns
        model_class = registry["ir.model"]
        self.assertTrue(issubclass(model_class, BaseModel))

    def test_inheritance_hooks_compatibility(self):
        """Test that model inheritance hooks still work."""
        # Test that _inherit mechanism works as expected
        from odoo.addons.base_geoengine.models.base import Base

        # Test that our Base class properly inherits from 'base'
        self.assertEqual(Base._inherit, "base")

        # Test that method inheritance/override works
        self.assertTrue(hasattr(Base, "search"))
        self.assertTrue(hasattr(Base, "fields_get"))

    def test_field_compute_and_store_compatibility(self):
        """Test that field compute and store mechanisms are stable."""
        # Test field properties that might be used in geo fields
        point_field = geo_fields.GeoPoint()

        # Test that field has expected ORM attributes
        expected_attrs = ["compute", "store", "readonly", "required", "index"]
        for attr in expected_attrs:
            self.assertTrue(
                hasattr(point_field, attr), f"Field missing expected attribute: {attr}"
            )

    def test_logging_interface_stability(self):
        """Test that logging interface used in our code is stable."""
        import logging

        # Test logging patterns used in our error handling
        logger = logging.getLogger(__name__)
        self.assertTrue(hasattr(logger, "warning"))
        self.assertTrue(hasattr(logger, "error"))
        self.assertTrue(hasattr(logger, "info"))

        # Test that we can log without errors
        logger.info("Test log message from ORM compatibility test")

    def test_sql_tools_compatibility(self):
        """Test that SQL tools we depend on are available."""
        from odoo.tools import SQL

        # Test SQL class availability and basic usage
        sql_obj = SQL("SELECT %s", "test")
        self.assertIsInstance(sql_obj, SQL)

        # Test that SQL objects can be created as we do in geo operators
        test_sql = SQL("ST_Contains(%s, %s)", "geom1", "geom2")
        self.assertIsInstance(test_sql, SQL)
