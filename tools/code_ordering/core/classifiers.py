#!/usr/bin/env python3
"""
Unified Classifiers for Code Elements

Provides consistent classification interfaces for various code elements.

Author: Agromarin Tools
Version: 1.0.0
"""

import ast

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from .patterns import OdooPatterns


@dataclass
class ClassificationResult:
    """Result of a classification operation."""

    category: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseClassifier(ABC):
    """Abstract base class for all classifiers."""

    @abstractmethod
    def classify(
        self, element: Any, context: Optional[Dict] = None
    ) -> ClassificationResult:
        """
        Classify an element.

        Args:
            element: Element to classify
            context: Optional context information

        Returns:
            ClassificationResult with category and metadata
        """
        pass


class FieldClassifier(BaseClassifier):
    """Unified field classifier supporting multiple strategies.

    This consolidates field classification logic from multiple sources
    to eliminate redundancy and ensure consistency.
    """

    # Semantic patterns for field classification

    def __init__(self, strategy: str = "semantic"):
        """
        Initialize field classifier.

        Args:
            strategy: Classification strategy ("semantic", "type", or "strict")
        """
        self.strategy = strategy

    def classify(
        self, element: Any, context: Optional[Dict] = None
    ) -> ClassificationResult:
        """Classify a field based on the selected strategy."""
        if self.strategy == "semantic":
            return self._classify_semantic(element, context)
        elif self.strategy == "type":
            return self._classify_by_type(element, context)
        else:  # strict
            return self._classify_strict(element, context)

    def _classify_semantic(
        self, element: Any, context: Optional[Dict] = None
    ) -> ClassificationResult:
        """Classify field based on semantic meaning."""
        context = context or {}
        field_name = context.get("field_name", "")
        field_type = context.get("field_type")
        is_computed = context.get("is_computed", False)
        is_related = context.get("is_related", False)

        # Skip model attributes and private non-fields
        if field_name.startswith("_"):
            return ClassificationResult("INTERNAL", metadata={"private": True})

        # Check if computed
        if is_computed:
            return ClassificationResult("COMPUTED", metadata={"computed": True})

        # Check patterns
        for group_name, patterns in OdooPatterns.SEMANTIC_PATTERNS.items():
            # Check exact matches
            if "exact" in patterns and field_name.lower() in patterns["exact"]:
                return ClassificationResult(
                    group_name, metadata={"match_type": "exact"}
                )

            # Check suffix patterns
            if "suffix" in patterns:
                for suffix in patterns["suffix"]:
                    if field_name.endswith(suffix):
                        return ClassificationResult(
                            group_name, metadata={"match_type": "suffix"}
                        )

            # Check prefix patterns
            if "prefix" in patterns:
                for prefix in patterns["prefix"]:
                    if field_name.startswith(prefix):
                        return ClassificationResult(
                            group_name, metadata={"match_type": "prefix"}
                        )

            # Check field types
            if "field_types" in patterns and field_type in patterns["field_types"]:
                return ClassificationResult(
                    group_name, metadata={"match_type": "field_type"}
                )

        return ClassificationResult("ATTRIBUTES")

    def _classify_by_type(
        self, element: Any, context: Optional[Dict] = None
    ) -> ClassificationResult:
        """Classify field based on field type only."""
        context = context or {}
        field_type = context.get("field_type", "Unknown")
        return ClassificationResult(
            f"TYPE_{field_type.upper()}", metadata={"field_type": field_type}
        )

    def _classify_strict(
        self, element: Any, context: Optional[Dict] = None
    ) -> ClassificationResult:
        """Classify field using strict AgroMarin ordering."""
        context = context or {}
        field_type = context.get("field_type")
        is_computed = context.get("is_computed", False)
        if is_computed:
            return ClassificationResult("COMPUTED", metadata={"computed": True})
        elif field_type:
            return ClassificationResult(
                f"TYPE_{field_type.upper()}", metadata={"field_type": field_type}
            )
        else:
            return ClassificationResult("UNKNOWN")

    @staticmethod
    def extract_field_info(field_node: ast.AST) -> Dict[str, Any]:
        """
        Extract field information from an AST node.

        Args:
            field_node: AST node representing a field assignment

        Returns:
            Dictionary with field_name, field_type, is_computed, is_related
        """
        info = {
            "field_name": None,
            "field_type": None,
            "is_computed": False,
            "is_related": False,
            "related_field_base": None,
        }

        if isinstance(field_node, ast.Assign):
            # Get field name
            for target in field_node.targets:
                if isinstance(target, ast.Name):
                    info["field_name"] = target.id
                    break

            # Get field type and attributes
            if field_node.value and isinstance(field_node.value, ast.Call):
                # Extract field type
                if hasattr(field_node.value.func, "attr"):
                    info["field_type"] = field_node.value.func.attr
                elif hasattr(field_node.value.func, "id"):
                    info["field_type"] = field_node.value.func.id

                # Check for special attributes
                for keyword in field_node.value.keywords:
                    if keyword.arg == "compute":
                        info["is_computed"] = True
                    elif keyword.arg == "related":
                        info["is_related"] = True
                        related_path = None
                        if isinstance(keyword.value, ast.Constant):
                            related_path = keyword.value.value
                        elif isinstance(keyword.value, ast.Str):  # Python < 3.8
                            related_path = keyword.value.s

                        # Extract the base field (first part before '.')
                        if related_path and "." in related_path:
                            info["related_field_base"] = related_path.split(".")[0]
                        elif related_path:
                            info["related_field_base"] = related_path

        return info

    def classify_field_node(
        self, field_node: ast.AST, skip_related: bool = False
    ) -> Optional[str]:
        """
        Classify a field directly from its AST node.

        Args:
            field_node: AST node representing a field
            skip_related: If True, returns None for related fields

        Returns:
            Classification category or None
        """
        info = self.extract_field_info(field_node)

        # Skip related fields if requested
        if skip_related and info["is_related"]:
            return None

        # Create context for classification
        context = {
            "field_name": info["field_name"],
            "field_type": info["field_type"],
            "is_computed": info["is_computed"],
            "is_related": info["is_related"],
        }

        result = self.classify(field_node, context)
        return result.category

    @staticmethod
    def get_related_field_base(field_node: ast.AST) -> Optional[str]:
        """
        Extract the base field name from a related field.

        For example, if related='partner_id.name', returns 'partner_id'.
        Returns None if the field is not a related field.
        """
        info = FieldClassifier.extract_field_info(field_node)
        if info.get("is_related") and "related_field_base" in info:
            return info["related_field_base"]
        return None


class MethodClassifier(BaseClassifier):
    """Unified method classifier using centralized patterns."""

    # Method type patterns (reference to centralized patterns)
    METHOD_PATTERNS = OdooPatterns.METHOD_PATTERNS

    def classify(
        self, element: Any, context: Optional[Dict] = None
    ) -> ClassificationResult:
        """Classify a method based on its name and decorators."""
        context = context or {}
        method_name = context.get("method_name", "")
        decorators = context.get("decorators", [])

        # Check decorators first (highest priority)
        has_depends_decorator = False
        has_onchange_decorator = False
        has_model_decorator = False

        for decorator in decorators:
            if "constrains" in decorator:
                return ClassificationResult(
                    "CONSTRAINTS",
                    metadata={"decorator": "constrains"},
                )
            elif "ondelete" in decorator:
                return ClassificationResult(
                    "CRUD",
                    metadata={"decorator": "ondelete"},
                )
            elif "model" in decorator and "model_create_multi" not in decorator:
                has_model_decorator = True
            elif "depends" in decorator:
                has_depends_decorator = True
            elif "onchange" in decorator:
                has_onchange_decorator = True

        # API MODEL: has @api.model decorator
        if has_model_decorator:
            return ClassificationResult(
                "API_MODEL",
                metadata={"decorator": "model"},
            )

        # COMPUTE: has @api.depends OR (has _compute_ prefix AND @api.depends)
        # In practice, any method with @api.depends is a compute method
        if has_depends_decorator:
            return ClassificationResult(
                "COMPUTE",
                metadata={"decorator": "depends"},
            )

        # ONCHANGE: must have @api.onchange decorator
        if has_onchange_decorator:
            return ClassificationResult(
                "ONCHANGE",
                metadata={"decorator": "onchange"},
            )

        # Check method name patterns
        for category, patterns in self.METHOD_PATTERNS.items():
            for pattern in patterns:
                # For CRUD methods, only match exact names (not substrings)
                if category == "CRUD":
                    if method_name == pattern:
                        return ClassificationResult(
                            category, metadata={"pattern": pattern}
                        )
                # For other categories, check if pattern is in method name
                elif pattern in method_name:
                    return ClassificationResult(category, metadata={"pattern": pattern})

        # Private vs public
        if method_name.startswith("_"):
            return ClassificationResult("PRIVATE")
        else:
            return ClassificationResult("PUBLIC")

    def classify_method_node(
        self, method_node: ast.FunctionDef, decorators: List[str] = None
    ) -> str:
        """
        Classify a method directly from its AST node.

        Args:
            method_node: AST node representing a method
            decorators: Optional list of decorator names

        Returns:
            Classification category
        """
        if decorators is None:
            decorators = []
            for decorator in method_node.decorator_list:
                if isinstance(decorator, ast.Name):
                    decorators.append(decorator.id)
                elif isinstance(decorator, ast.Attribute):
                    decorators.append(decorator.attr)
                elif isinstance(decorator, ast.Call):
                    if isinstance(decorator.func, ast.Name):
                        decorators.append(decorator.func.id)
                    elif isinstance(decorator.func, ast.Attribute):
                        decorators.append(decorator.func.attr)

        context = {
            "method_name": method_node.name,
            "decorators": decorators,
        }

        result = self.classify(method_node, context)
        return result.category


class ModelElementClassifier(BaseClassifier):
    """Classifies model-level elements (attributes, indexes, constraints)."""

    @staticmethod
    def is_model_attribute(name: str, source: str = "") -> bool:
        """Check if an assignment is a model attribute."""
        # Standard Odoo model attributes
        standard_attrs = OdooPatterns.MODEL_ATTRIBUTES
        if name in standard_attrs:
            return True

        # For other _ prefixed items, check the source
        if name.startswith("_") and source:
            # It's a model attribute if it uses models.* but not fields.*, Index, or Constraint
            if (
                "models." in source
                and "fields." not in source
                and "models.Index" not in source
                and "models.Constraint" not in source
            ):
                return True

        return False

    @staticmethod
    def is_model_index(name: str, source: str = "") -> bool:
        """Check if an assignment is a model index."""
        # Check if it's a models.Index assignment
        if source and "models.Index" in source:
            return True
        # Also check for _index suffix pattern
        if name.endswith("_index") and name.startswith("_"):
            return True
        return False

    @staticmethod
    def is_sql_constraint(name: str, source: str = "") -> bool:
        """Check if an assignment is a SQL constraint."""
        if name == "_sql_constraints":
            return True
        # Check for models.Constraint
        if source and "models.Constraint" in source:
            return True
        return False

    def classify(
        self, element: Any, context: Optional[Dict] = None
    ) -> ClassificationResult:
        """Classify a model-level element."""
        context = context or {}
        name = context.get("name", "")
        source = context.get("source", "")

        if self.is_model_attribute(name, source):
            return ClassificationResult("MODEL_ATTRIBUTE", metadata={"name": name})
        elif self.is_model_index(name, source):
            return ClassificationResult("MODEL_INDEX", metadata={"name": name})
        elif self.is_sql_constraint(name, source):
            return ClassificationResult("SQL_CONSTRAINT", metadata={"name": name})
        else:
            return ClassificationResult("UNKNOWN", metadata={"name": name})


class ImportClassifier(BaseClassifier):
    """Classifies import statements."""

    def __init__(self, odoo_patterns: Optional[Dict] = None):
        """
        Initialize import classifier.

        Args:
            odoo_patterns: Patterns for identifying Odoo imports
        """
        self.odoo_patterns = odoo_patterns or OdooPatterns.IMPORT_PATTERNS
        self._stdlib_modules = None

    def classify(
        self, element: Any, context: Optional[Dict] = None
    ) -> ClassificationResult:
        """Classify an import statement."""
        context = context or {}
        module_name = context.get("module_name", "")
        is_relative = context.get("is_relative", False)

        if is_relative:
            return ClassificationResult(
                "relative", metadata={"relative_level": context.get("level", 0)}
            )

        # Check patterns
        if self._is_odoo_addon(module_name):
            return ClassificationResult("odoo_addons")
        elif self._is_odoo_import(module_name):
            return ClassificationResult("odoo")
        elif self._is_stdlib(module_name):
            return ClassificationResult("python_stdlib")
        else:
            return ClassificationResult("third_party")

    def _is_odoo_import(self, module: str) -> bool:
        """Check if module is an Odoo core import."""
        return any(
            module.startswith(pattern) for pattern in self.odoo_patterns.get("odoo", [])
        )

    def _is_odoo_addon(self, module: str) -> bool:
        """Check if module is an Odoo addon import."""
        return any(
            module.startswith(pattern)
            for pattern in self.odoo_patterns.get("odoo_addons", [])
        )

    def _is_stdlib(self, module: str) -> bool:
        """Check if module is a Python standard library module."""
        if self._stdlib_modules is None:
            import sys

            self._stdlib_modules = set(sys.stdlib_module_names)

        base_module = module.split(".")[0]
        return base_module in self._stdlib_modules
