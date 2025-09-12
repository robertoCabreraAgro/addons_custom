#!/usr/bin/env python3
"""
Semantic Code Reorganizer - Improved strategy for Odoo code organization.

This module implements a context-aware, semantic grouping approach that
understands Odoo patterns and organizes code based on business logic
rather than just technical structure.
"""

import ast
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from pathlib import Path

from .base_patterns import BaseASTProcessor
from .element_extractor import ElementExtractor, ElementType, UnifiedElement


@dataclass
class SemanticConfig:
    """Configuration for semantic reorganization."""

    # Strategy selection
    reorder_strategy: str = "semantic"  # "semantic", "strict", "hybrid", "custom"

    # Field ordering configuration
    group_related_fields: bool = True  # Keep _ids near _id
    preserve_field_comments: bool = True
    respect_field_dependencies: bool = True

    # Method ordering configuration
    group_by_feature: bool = True  # Group related business logic
    preserve_method_flow: bool = True  # Keep call chains together
    respect_method_dependencies: bool = True

    # Smart features
    auto_detect_patterns: bool = True
    learn_from_codebase: bool = False  # Analyze existing patterns

    # Section headers
    add_section_headers: bool = True
    section_separator: str = "-" * 60

    # Field semantic groups (order matters)
    field_groups: List[str] = field(
        default_factory=lambda: [
            "IDENTIFIERS",
            "ATTRIBUTES",
            "RELATIONSHIPS",
            "MEASURES",
            "DATES",
            "CONTENT",
            "COMPUTED",
            "TECHNICAL",
        ]
    )

    # Method semantic groups (order matters)
    method_groups: List[str] = field(
        default_factory=lambda: [
            "INITIALIZATION",
            "CRUD",
            "COMPUTED_FIELDS",
            "INVERSE_FIELDS",
            "SEARCH_FIELDS",
            "ONCHANGE",
            "CONSTRAINTS",
            "ACTIONS",
            "BUSINESS_LOGIC",
            "UTILITIES",
        ]
    )


class FieldClassifier:
    """Classifies fields based on semantic meaning."""

    # Pattern definitions for field classification
    PATTERNS = {
        "IDENTIFIERS": {
            "exact": ["name", "code", "default_code", "barcode", "ref", "reference"],
            "suffix": ["_ref", "_code", "_number"],
            "prefix": [],
        },
        "ATTRIBUTES": {
            "exact": ["active", "sequence", "priority", "state", "type", "color"],
            "suffix": ["_state", "_type", "_mode"],
            "prefix": ["is_", "has_", "can_"],
        },
        "RELATIONSHIPS": {
            "suffix": ["_id", "_ids"],
            "field_types": ["Many2one", "One2many", "Many2many"],
        },
        "MEASURES": {
            "exact": ["quantity", "price", "amount", "volume", "weight", "qty"],
            "suffix": ["_quantity", "_qty", "_amount", "_price", "_cost", "_total"],
            "prefix": ["total_", "sum_", "avg_"],
        },
        "DATES": {
            "exact": ["date", "datetime"],
            "suffix": ["_date", "_datetime", "_time", "_at"],
            "prefix": ["date_", "datetime_"],
        },
        "CONTENT": {
            "exact": ["description", "notes", "comment"],
            "suffix": ["_description", "_notes", "_text", "_html"],
            "field_types": ["Text", "Html"],
        },
    }

    def classify_field(
        self, field_node: ast.AST, field_name: str, processor: BaseASTProcessor
    ) -> str:
        """Classify a field based on its semantic meaning."""

        # Check if it's computed
        if self._is_computed_field(field_node, processor):
            return "COMPUTED"

        # Check if it's technical/private
        if field_name.startswith("_"):
            return "TECHNICAL"

        # Get field type if available
        field_type = self._get_field_type(field_node, processor)

        # Check each pattern group
        for group_name, patterns in self.PATTERNS.items():
            # Check exact matches
            if "exact" in patterns and field_name.lower() in patterns["exact"]:
                return group_name

            # Check suffix patterns
            if "suffix" in patterns:
                for suffix in patterns["suffix"]:
                    if field_name.endswith(suffix):
                        return group_name

            # Check prefix patterns
            if "prefix" in patterns:
                for prefix in patterns["prefix"]:
                    if field_name.startswith(prefix):
                        return group_name

            # Check field types
            if "field_types" in patterns and field_type in patterns["field_types"]:
                return group_name

        # Default category
        return "ATTRIBUTES"

    def _is_computed_field(
        self, field_node: ast.AST, processor: BaseASTProcessor
    ) -> bool:
        """Check if a field is computed."""
        if isinstance(field_node, ast.Assign) and field_node.value:
            if isinstance(field_node.value, ast.Call):
                # Check for compute parameter
                for keyword in field_node.value.keywords:
                    if keyword.arg == "compute":
                        return True
        return False

    def _get_field_type(
        self, field_node: ast.AST, processor: BaseASTProcessor
    ) -> Optional[str]:
        """Extract field type from AST node."""
        if isinstance(field_node, ast.Assign) and field_node.value:
            if isinstance(field_node.value, ast.Call):
                if hasattr(field_node.value.func, "attr"):
                    return field_node.value.func.attr
                elif hasattr(field_node.value.func, "id"):
                    return field_node.value.func.id
        return None


class MethodClassifier:
    """Classifies methods based on semantic meaning and lifecycle."""

    PATTERNS = {
        "INITIALIZATION": ["default_get", "_default_*", "__init__"],
        "CRUD": ["create", "write", "unlink", "read", "copy", "copy_data"],
        "COMPUTED_FIELDS": ["_compute_*"],
        "INVERSE_FIELDS": ["_inverse_*", "_set_*"],
        "SEARCH_FIELDS": ["_search_*"],
        "ONCHANGE": ["_onchange_*", "onchange_*"],
        "CONSTRAINTS": ["_check_*", "_validate_*", "_constrains_*"],
        "ACTIONS": ["action_*", "button_*"],
        "BUSINESS_LOGIC": [],  # Will be detected by context
        "UTILITIES": ["_get_*", "_prepare_*", "_build_*", "_format_*"],
    }

    def classify_method(
        self, method_node: ast.FunctionDef, decorators: List[str]
    ) -> str:
        """Classify a method based on its semantic meaning."""
        method_name = method_node.name

        # Check decorators first
        for decorator in decorators:
            if "constrains" in decorator:
                return "CONSTRAINTS"
            elif "depends" in decorator and "_compute_" in method_name:
                return "COMPUTED_FIELDS"
            elif "onchange" in decorator:
                return "ONCHANGE"

        # Check method patterns
        for category, patterns in self.PATTERNS.items():
            for pattern in patterns:
                if "*" in pattern:
                    # Wildcard pattern
                    regex = pattern.replace("*", ".*")
                    if re.match(regex, method_name):
                        return category
                else:
                    # Exact match
                    if method_name == pattern:
                        return category

        # Check if it's a private utility
        if method_name.startswith("_"):
            return "UTILITIES"

        # Default to business logic for public methods
        return "BUSINESS_LOGIC"

    def get_method_priority(self, method_name: str, category: str) -> int:
        """Get priority for ordering within a category."""
        # Define priority for specific methods within categories
        priority_map = {
            "CRUD": {
                "default_get": 1,
                "create": 2,
                "write": 3,
                "read": 4,
                "copy": 5,
                "copy_data": 6,
                "unlink": 7,
            },
            "INITIALIZATION": {
                "__init__": 1,
                "default_get": 2,
            },
        }

        if category in priority_map and method_name in priority_map[category]:
            return priority_map[category][method_name]

        return 100  # Default priority


class DependencyAnalyzer:
    """Analyzes dependencies between fields and methods."""

    def __init__(self, processor: BaseASTProcessor):
        self.processor = processor
        self.field_dependencies = defaultdict(set)
        self.method_dependencies = defaultdict(set)

    def analyze_field_dependencies(
        self, class_node: ast.ClassDef
    ) -> Dict[str, Set[str]]:
        """Analyze dependencies between fields."""
        dependencies = defaultdict(set)

        for node in ast.walk(class_node):
            if isinstance(node, ast.Assign):
                if hasattr(node, "targets") and node.targets:
                    target = node.targets[0]
                    if isinstance(target, ast.Name):
                        field_name = target.id

                        # Check for related fields
                        if isinstance(node.value, ast.Call):
                            for keyword in node.value.keywords:
                                if keyword.arg == "related":
                                    # Extract related field
                                    if isinstance(keyword.value, ast.Constant):
                                        related = keyword.value.value
                                        base_field = related.split(".")[0]
                                        dependencies[field_name].add(base_field)

                                elif keyword.arg == "compute":
                                    # Extract compute method
                                    if isinstance(keyword.value, ast.Constant):
                                        compute_method = keyword.value.value
                                        dependencies[field_name].add(compute_method)

        return dependencies

    def analyze_method_dependencies(
        self, class_node: ast.ClassDef
    ) -> Dict[str, Set[str]]:
        """Analyze dependencies between methods."""
        dependencies = defaultdict(set)

        for node in ast.walk(class_node):
            if isinstance(node, ast.FunctionDef):
                method_name = node.name

                # Find method calls within this method
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Attribute):
                            if isinstance(child.func.value, ast.Name):
                                if child.func.value.id == "self":
                                    called_method = child.func.attr
                                    dependencies[method_name].add(called_method)

        return dependencies


class SemanticReorganizer:
    """Main class for semantic code reorganization."""

    def __init__(self, config: Optional[SemanticConfig] = None):
        self.config = config or SemanticConfig()
        self.field_classifier = FieldClassifier()
        self.method_classifier = MethodClassifier()

    def reorganize_class(
        self, class_node: ast.ClassDef, processor: BaseASTProcessor
    ) -> List[str]:
        """Reorganize a class using semantic grouping."""
        lines = []

        # Extract class elements
        elements = processor.extract_class_elements(class_node)

        # Analyze dependencies if configured
        dependencies = {}
        if (
            self.config.respect_field_dependencies
            or self.config.respect_method_dependencies
        ):
            analyzer = DependencyAnalyzer(processor)
            dependencies["fields"] = analyzer.analyze_field_dependencies(class_node)
            dependencies["methods"] = analyzer.analyze_method_dependencies(class_node)

        # Add class definition
        class_def = processor.safe_unparse(class_node)
        class_lines = class_def.split("\n")
        for i, line in enumerate(class_lines):
            if line.strip().endswith(":"):
                lines.extend(class_lines[: i + 1])
                break

        # Add docstring if present
        docstring = processor.get_docstring(class_node)
        if docstring:
            lines.append(f'    """{docstring}"""')
            lines.append("")

        # Process model attributes
        model_attrs = self._extract_model_attributes(class_node, processor)
        if model_attrs:
            if self.config.add_section_headers:
                lines.extend(self._format_section_header("MODEL ATTRIBUTES"))
            for attr in model_attrs:
                lines.append(f"    {attr}")
            lines.append("")

        # Process fields semantically
        field_groups = self._group_fields_semantically(
            elements.get("fields", []), processor
        )
        for group_name in self.config.field_groups:
            if group_name in field_groups and field_groups[group_name]:
                if self.config.add_section_headers:
                    lines.extend(self._format_section_header(f"{group_name} FIELDS"))

                # Sort fields within group if needed
                fields = field_groups[group_name]
                if self.config.group_related_fields:
                    fields = self._sort_fields_related(fields, processor)

                for field_node in fields:
                    field_source = processor.get_source_segment(field_node)
                    if field_source:
                        for line in field_source.split("\n"):
                            lines.append(f"    {line}")
                lines.append("")

        # Process SQL constraints
        sql_constraints = self._extract_sql_constraints(class_node, processor)
        if sql_constraints:
            if self.config.add_section_headers:
                lines.extend(self._format_section_header("SQL CONSTRAINTS"))
            for constraint in sql_constraints:
                lines.append(f"    {constraint}")
            lines.append("")

        # Process methods semantically
        method_groups = self._group_methods_semantically(
            elements.get("methods", []), processor
        )
        for group_name in self.config.method_groups:
            if group_name in method_groups and method_groups[group_name]:
                if self.config.add_section_headers:
                    lines.extend(self._format_section_header(f"{group_name}"))

                # Sort methods within group
                methods = method_groups[group_name]
                if self.config.preserve_method_flow:
                    methods = self._sort_by_dependencies(
                        methods, dependencies.get("methods", {})
                    )
                else:
                    methods = self._sort_methods_in_group(methods, group_name)

                for method_node in methods:
                    # Add decorators
                    if (
                        hasattr(method_node, "decorator_list")
                        and method_node.decorator_list
                    ):
                        for decorator in method_node.decorator_list:
                            decorator_source = processor.get_decorator_source(decorator)
                            lines.append(f"    {decorator_source}")

                    # Add method
                    method_source = processor.get_source_segment(method_node)
                    if method_source:
                        for line in method_source.split("\n"):
                            lines.append(f"    {line}")
                        lines.append("")

        return lines

    def _group_fields_semantically(
        self, fields: List[ast.AST], processor: BaseASTProcessor
    ) -> Dict[str, List[ast.AST]]:
        """Group fields by semantic meaning."""
        groups = defaultdict(list)

        for field_node in fields:
            if isinstance(field_node, ast.Assign) and field_node.targets:
                target = field_node.targets[0]
                if isinstance(target, ast.Name):
                    field_name = target.id
                    category = self.field_classifier.classify_field(
                        field_node, field_name, processor
                    )
                    groups[category].append(field_node)

        return groups

    def _group_methods_semantically(
        self, methods: List[ast.AST], processor: BaseASTProcessor
    ) -> Dict[str, List[ast.AST]]:
        """Group methods by semantic meaning."""
        groups = defaultdict(list)

        for method_node in methods:
            if isinstance(method_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decorators = [
                    processor.extract_decorator_name(d) or ""
                    for d in method_node.decorator_list
                ]
                category = self.method_classifier.classify_method(
                    method_node, decorators
                )
                groups[category].append(method_node)

        return groups

    def _sort_fields_related(
        self, fields: List[ast.AST], processor: BaseASTProcessor
    ) -> List[ast.AST]:
        """Sort fields keeping related ones together (e.g., partner_id near partner_ids)."""
        field_map = {}
        for field_node in fields:
            if isinstance(field_node, ast.Assign) and field_node.targets:
                target = field_node.targets[0]
                if isinstance(target, ast.Name):
                    field_map[target.id] = field_node

        sorted_fields = []
        processed = set()

        for field_name in sorted(field_map.keys()):
            if field_name in processed:
                continue

            # Add the field
            sorted_fields.append(field_map[field_name])
            processed.add(field_name)

            # Look for related fields (singular/plural)
            base_name = field_name.rstrip("s").rstrip("_id").rstrip("_ids")
            for other_name in field_map:
                if other_name != field_name and other_name not in processed:
                    other_base = other_name.rstrip("s").rstrip("_id").rstrip("_ids")
                    if base_name == other_base:
                        sorted_fields.append(field_map[other_name])
                        processed.add(other_name)

        return sorted_fields

    def _sort_methods_in_group(
        self, methods: List[ast.AST], group_name: str
    ) -> List[ast.AST]:
        """Sort methods within a group."""
        method_list = []
        for method_node in methods:
            priority = self.method_classifier.get_method_priority(
                method_node.name, group_name
            )
            method_list.append((priority, method_node.name, method_node))

        # Sort by priority, then by name
        method_list.sort(key=lambda x: (x[0], x[1]))
        return [m[2] for m in method_list]

    def _sort_by_dependencies(
        self, methods: List[ast.AST], dependencies: Dict[str, Set[str]]
    ) -> List[ast.AST]:
        """Sort methods respecting their dependencies."""
        # Create a dependency graph
        method_map = {m.name: m for m in methods if hasattr(m, "name")}
        sorted_methods = []
        visited = set()

        def visit(method_name):
            if method_name in visited or method_name not in method_map:
                return
            visited.add(method_name)

            # Visit dependencies first
            for dep in dependencies.get(method_name, []):
                if dep in method_map:
                    visit(dep)

            sorted_methods.append(method_map[method_name])

        # Visit all methods
        for method_name in sorted(method_map.keys()):
            visit(method_name)

        return sorted_methods

    def _extract_model_attributes(
        self, class_node: ast.ClassDef, processor: BaseASTProcessor
    ) -> List[str]:
        """Extract model attributes (_name, _inherit, etc.)."""
        attributes = []
        model_attrs = [
            "_name",
            "_inherit",
            "_inherits",
            "_description",
            "_rec_name",
            "_order",
            "_table",
            "_sql_constraints",
            "_parent_name",
            "_parent_store",
        ]

        for node in class_node.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in model_attrs:
                        attributes.append(processor.safe_unparse(node))

        return attributes

    def _extract_sql_constraints(
        self, class_node: ast.ClassDef, processor: BaseASTProcessor
    ) -> List[str]:
        """Extract SQL constraints."""
        constraints = []

        for node in class_node.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "_sql_constraints":
                        constraints.append(processor.safe_unparse(node))

        return constraints

    def _format_section_header(self, title: str) -> List[str]:
        """Format a section header."""
        if not self.config.add_section_headers:
            return []

        separator = self.config.section_separator
        return [
            f"    # {separator}",
            f"    # {title}",
            f"    # {separator}",
        ]
