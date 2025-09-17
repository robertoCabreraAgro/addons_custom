#!/usr/bin/env python3
"""
Ordering functions and patterns for code elements.

This module combines pattern definitions, classification and sorting operations
for code elements. Patterns define the rules and constants, classification
determines the category of an element, and sorting orders elements based on
their categories. These operations form a natural pipeline for code organization.

The module provides:
- Pattern definitions for Odoo-specific code organization
- Field classification and sorting (semantic, type-based, strict)
- Method classification and sorting (by category)
- Import classification and sorting (by group)
- Utility functions for element analysis
"""

import ast
import isort
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.classification_rule_method import (
    ClassificationRuleMethod,
    get_default_method_rules,
)
from core.classification_rule_field import (
    ClassificationRuleField,
    get_default_field_rules,
)
from core.formatting import format_section_header


logger = logging.getLogger(__name__)


# ============================================================
# PATTERN DEFINITIONS
# ============================================================


class Ordering:
    """Centralized Odoo-specific patterns and reorganization logic."""

    def __init__(self, config=None, content: str = "", filepath: Path | None = None):
        """Initialize Ordering with configuration and optional content.

        Args:
            config: Configuration object with field_strategy, add_section_headers, etc.
            content: Python source code content for processing
            filepath: Optional path to the source file
        """
        self.config = config or self._get_default_config()
        self.content = content
        self.filepath = filepath
        self._tree = None
        self._method_rules = get_default_method_rules()
        self._field_rules = get_default_field_rules()

    def _get_default_config(self):
        """Get default configuration when none is provided."""

        @dataclass
        class DefaultConfig:
            field_strategy: str = "semantic"
            add_section_headers: bool = True

        return DefaultConfig()

    @property
    def tree(self) -> ast.Module:
        """Get the parsed AST tree, parsing if necessary."""
        if self._tree is None:
            try:
                self._tree = ast.parse(self.content)
                logger.debug(f"Successfully parsed {self.filepath or 'content'}")
            except SyntaxError as e:
                logger.error(f"Syntax error parsing {self.filepath or 'content'}: {e}")
                raise
        return self._tree

    def set_tree(self, tree: ast.Module):
        """Set the AST tree directly (used when tree is already parsed)."""
        self._tree = tree

    # ============================================================
    # PATTERNS
    # ============================================================

    MODEL_ATTRIBUTES: list[str] = [
        "_name",
        "_inherits",
        "_inherit",
        "_description",
        "_table",
        "_table_query",
        "_sequence",
        "_active_name",
        "_date_name",
        "_fold_name",
        "_parent_name",
        "_parent_store",
        "_parent_order",
        "_rec_name",
        "_rec_names_search",
        "_auto",
        "_abstract",
        "_check_company_auto",
        "_custom",
        "_depends",
        "_register",
        "_transient",
        "_transient_max_count",
        "_transient_max_hours",
        "_module",
        "_translate",
        "_allow_sudo_commands",
        "_log_access",
        "_order",
        "_check_company_domain",
    ]

    # Field-type specific attribute ordering
    # Each field type has its own optimal attribute order
    FIELD_TYPE_ATTRIBUTES: dict[str, list[str]] = {
        # Relational fields
        "Many2one": [
            "related",
            "comodel_name",
            "string",
            "required",
            "default",
            "compute",
            "store",
            "precompute",
            "readonly",
            "inverse",
            "search",
            "company_dependent",
            "domain",
            "context",
            "ondelete",
            "auto_join",
            "copy",
            "groups",
            "index",
            "tracking",
            "help",
        ],
        "One2many": [
            "comodel_name",
            "inverse_name",
            "string",
            "compute",
            "store",
            "readonly",
            "domain",
            "context",
            "auto_join",
            "copy",
            "groups",
            "help",
        ],
        "Many2many": [
            "related",
            "comodel_name",
            "relation",
            "column1",
            "column2",
            "string",
            "required",
            "compute",
            "store",
            "readonly",
            "inverse",
            "search",
            "domain",
            "context",
            "copy",
            "groups",
            "tracking",
            "help",
        ],
        # Basic fields
        "Char": [
            "related",
            "string",
            "required",
            "size",
            "trim",
            "translate",
            "default",
            "compute",
            "store",
            "readonly",
            "inverse",
            "search",
            "copy",
            "groups",
            "index",
            "tracking",
            "help",
        ],
        "Text": [
            "related",
            "string",
            "required",
            "translate",
            "default",
            "compute",
            "store",
            "readonly",
            "inverse",
            "search",
            "copy",
            "groups",
            "tracking",
            "help",
        ],
        "Html": [
            "related",
            "string",
            "required",
            "translate",
            "sanitize",
            "sanitize_tags",
            "sanitize_attributes",
            "sanitize_style",
            "strip_style",
            "strip_classes",
            "compute",
            "store",
            "readonly",
            "inverse",
            "search",
            "default",
            "copy",
            "groups",
            "tracking",
            "help",
        ],
        # Numeric fields
        "Integer": [
            "related",
            "string",
            "required",
            "compute",
            "store",
            "readonly",
            "inverse",
            "search",
            "default",
            "copy",
            "groups",
            "index",
            "tracking",
            "help",
        ],
        "Float": [
            "related",
            "string",
            "digits",
            "required",
            "compute",
            "store",
            "readonly",
            "inverse",
            "search",
            "default",
            "copy",
            "groups",
            "index",
            "group_operator",
            "tracking",
            "help",
        ],
        "Monetary": [
            "related",
            "string",
            "currency_field",
            "required",
            "compute",
            "store",
            "readonly",
            "inverse",
            "search",
            "default",
            "copy",
            "groups",
            "tracking",
            "help",
        ],
        # Date/time fields
        "Date": [
            "related",
            "string",
            "required",
            "compute",
            "store",
            "readonly",
            "inverse",
            "search",
            "default",
            "copy",
            "groups",
            "index",
            "tracking",
            "help",
        ],
        "Datetime": [
            "related",
            "string",
            "required",
            "compute",
            "store",
            "readonly",
            "inverse",
            "search",
            "default",
            "copy",
            "groups",
            "index",
            "tracking",
            "help",
        ],
        # Selection field
        "Selection": [
            "related",
            "selection",
            "string",
            "required",
            "compute",
            "store",
            "readonly",
            "inverse",
            "search",
            "default",
            "copy",
            "groups",
            "index",
            "tracking",
            "help",
        ],
        # Boolean field
        "Boolean": [
            "related",
            "string",
            "required",
            "compute",
            "store",
            "readonly",
            "inverse",
            "search",
            "default",
            "copy",
            "groups",
            "index",
            "tracking",
            "help",
        ],
        # Binary fields
        "Binary": [
            "related",
            "string",
            "required",
            "readonly",
            "attachment",
            "compute",
            "store",
            "inverse",
            "search",
            "default",
            "copy",
            "groups",
            "help",
        ],
        "Image": [
            "related",
            "string",
            "max_width",
            "max_height",
            "verify_resolution",
            "required",
            "readonly",
            "attachment",
            "compute",
            "store",
            "inverse",
            "search",
            "default",
            "copy",
            "groups",
            "help",
        ],
        # Special fields
        "Reference": [
            "related",
            "selection",
            "string",
            "required",
            "readonly",
            "compute",
            "store",
            "inverse",
            "search",
            "default",
            "copy",
            "groups",
            "help",
        ],
        "Json": [
            "related",
            "string",
            "required",
            "readonly",
            "compute",
            "store",
            "inverse",
            "search",
            "default",
            "copy",
            "groups",
            "help",
        ],
        "Properties": [
            "string",
            "definition",
            "required",
            "readonly",
            "compute",
            "store",
            "inverse",
            "search",
            "copy",
            "groups",
            "help",
        ],
    }

    # Generic fallback order for unknown field types
    FIELD_ATTRIBUTE_GENERIC: list[str] = [
        "related",
        # Primary attributes
        "string",
        "required",
        "default",
        "translate",
        # Compute attributes
        "compute",
        "store",
        "readonly",
        "inverse",
        "search",
        "depends",
        # Default and copy
        "copy",
        # Constraints and UI
        "tracking",
        "groups",
        "index",
        "states",
        "company_dependent",
        # Help and documentation
        "deprecated",
        "oldname",
        "help",
    ]

    SECTION_HEADERS: dict[str, str] = {
        "MODEL_ATTRIBUTES": "CLASS ATTRIBUTES",
        "FIELDS": "FIELDS",
        "COMPUTED_FIELDS": "COMPUTED FIELDS",
        "SQL_CONSTRAINTS": "SQL CONSTRAINTS",
        "MODEL_INDEXES": "MODEL INDEXES",
        "CRUD": "CRUD METHODS",
        "COMPUTE": "COMPUTE METHODS",
        "INVERSE": "INVERSE METHODS",
        "SEARCH": "SEARCH METHODS",
        "ONCHANGE": "ONCHANGE METHODS",
        "CONSTRAINT": "CONSTRAINT METHODS",
        "WORKFLOW": "WORKFLOW METHODS",
        "ACTIONS": "ACTION METHODS",
        "PREPARE": "PREPARE METHODS",
        "GETTER": "GETTER METHODS",
        "REPORT": "REPORT METHODS",
        "IMPORT_EXPORT": "IMPORT/EXPORT METHODS",
        "SECURITY": "SECURITY METHODS",
        "PORTAL": "PORTAL METHODS",
        "COMMUNICATION": "COMMUNICATION METHODS",
        "WIZARD": "WIZARD METHODS",
        "INTEGRATION": "INTEGRATION METHODS",
        "CRON": "SCHEDULED METHODS",
        "ACCOUNTING": "ACCOUNTING METHODS",
        "MANUFACTURING": "MANUFACTURING METHODS",
        "PRODUCT_CATALOG": "PRODUCT CATALOG MIXIN METHODS",
        "MAIL_THREAD": "MAIL THREAD METHODS",
        "OVERRIDE": "OVERRIDE METHODS",
        "API_MODEL": "API MODEL METHODS",
        "PUBLIC": "PUBLIC METHODS",
        "PRIVATE": "PRIVATE METHODS",
        "MISC": "MISCELLANEOUS",
    }

    SEMANTIC_PATTERNS: dict[str, dict[str, list[str]]] = {
        "IDENTIFIERS": {
            "exact": ["name", "code", "default_code", "barcode", "ref", "reference"],
            "suffix": ["_ref", "_code", "_number"],
        },
        "ATTRIBUTES": {
            "exact": ["active", "sequence", "priority", "state", "type", "color"],
            "suffix": ["_state", "_type", "_mode"],
            "prefix": ["is_", "has_", "can_"],
        },
        "GENEALOGY": {
            "exact": ["parent_id", "parent_path", "child_id", "child_ids"],
            "suffix": ["_parent_id", "_child_id", "_child_ids"],
            "prefix": ["parent_", "child_"],
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

    # ============================================================
    # PARSING & EXTRACTION
    # ============================================================

    def extract_imports(self) -> list[ast.stmt]:
        """Extract all import statements from the module.

        Returns:
            list[ast.stmt]: List of Import and ImportFrom nodes
        """
        imports = []
        for node in self.tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imports.append(node)
        return imports

    def extract_assignments(self) -> list[ast.Assign]:
        """Extract all top-level assignments (module-level variables).

        Returns:
            list[ast.Assign]: List of assignment nodes at module level
        """
        assignments = []
        for node in self.tree.body:
            if isinstance(node, (ast.Assign)):
                assignments.append(node)
        return assignments

    def extract_functions(self) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
        """Extract all top-level function definitions.

        Only returns functions at module level, not methods inside classes.

        Returns:
            list[Union[ast.FunctionDef, ast.AsyncFunctionDef]]: Module-level functions
        """
        functions = []
        for node in self.tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(node)
        return functions

    def extract_classes(self) -> list[ast.ClassDef]:
        """Extract all top-level class definitions.

        Returns:
            list[ast.ClassDef]: List of class definition nodes
        """
        classes = []
        for node in self.tree.body:
            if isinstance(node, ast.ClassDef):
                classes.append(node)
        return classes

    def extract_class_bases(self, class_node: ast.ClassDef) -> list:
        """Extract base classes from a class definition.

        Args:
            class_node: AST ClassDef node

        Returns:
            list: List of base class AST nodes, or ['models.Model'] as fallback
        """
        if not class_node.bases:
            return ["models.Model"]  # Fallback for Odoo
        bases = []
        for base in class_node.bases:
            bases.append(base)
        return bases

    def extract_class_elements(
        self,
        class_node: ast.ClassDef,
    ) -> dict[str, list[ast.AST] | dict[str, ast.AST]]:
        """Extract and categorize all elements from a class definition.

        Processes the class body to identify and categorize different types
        of class members including methods, fields, properties, and nested classes.

        Args:
            class_node: AST ClassDef node to analyze

        Returns:
            dict[str, list[ast.AST]]: Dictionary with keys:
                - 'decorators': Class decorators
                - 'docstring': Class docstring
                - 'model_attrs': Model attributes
                - 'properties': Property-decorated methods
                - 'class_vars': Nested classes
                - 'fields': Field assignments and annotated assignments
                - 'methods': Regular methods
                - 'class_bases': Base classes
        """
        elements = {
            "decorators": [],
            "class_bases": [],
            "docstring": [],
            "model_attrs": [],
            "class_vars": [],
            "properties": [],
            "fields": [],
            "methods": [],
        }

        elements["decorators"] = class_node.decorator_list
        elements["class_bases"] = self.extract_class_bases(class_node)

        if ast.get_docstring(class_node):
            for node in class_node.body:
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                    elements["docstring"].append(node)
                    break

        for node in class_node.body:
            if isinstance(node, (ast.ClassDef,)):
                # Nested classes
                elements["class_vars"].append(node)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check if it's a property
                if self._is_property(node):
                    elements["properties"].append(node)
                else:
                    elements["methods"].append(node)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                if hasattr(node, "targets") and node.targets:
                    if isinstance(node.targets[0], ast.Name):
                        name = node.targets[0].id
                        if name in self.MODEL_ATTRIBUTES:
                            elements["model_attrs"].append(node)
                        else:
                            reordered_node = self.sort_field_attributes(node)
                            elements["fields"].append(
                                reordered_node if reordered_node else node
                            )

        if elements["fields"]:
            elements["fields"] = self.group_fields_by_category(elements["methods"])

        if elements["methods"]:
            elements["methods"] = self.group_methods_by_category(elements["methods"])

        return elements

    def extract_elements(self) -> dict[str, list[ast.AST]]:
        """
        Extract all elements from the module, organized by type.

        Returns:
            Dictionary with keys:
            - 'imports': Import and ImportFrom nodes
            - 'module_vars': Top-level Assign nodes
            - 'functions': FunctionDef and AsyncFunctionDef nodes
            - 'classes': ClassDef nodes
        """
        elements = {
            "imports": [],
            "module_vars": [],
            "functions": [],
            "classes": [],
        }

        # Extract imports
        elements["imports"] = self.extract_imports()

        # Extract module-level variables
        elements["module_vars"] = self.extract_assignments()

        # Extract top-level functions
        elements["functions"] = self.extract_functions()

        # Extract classes
        elements["classes"] = self.extract_classes()

        return elements

    def extract_decorators(self, node: ast.FunctionDef) -> list[str]:
        """Extract decorator names from a method node.

        Args:
            node: AST FunctionDef node

        Returns:
            List of decorator names with @ prefix
        """
        decorators = []
        for decorator in node.decorator_list:
            decorator_name = self.get_decorator_name(decorator)
            if decorator_name:
                decorators.append(f"@{decorator_name}")
        return decorators

    # ============================================================
    # CLASSIFICATION FUNCTIONS
    # ============================================================

    def classify_model_element(self, node: ast.AST) -> str:
        """
        Classify a model-level element.

        Args:
            node: AST node

        Returns:
            Element type
        """
        if isinstance(node, ast.Assign):
            # Check for model attributes
            if any(isinstance(target, ast.Name) for target in node.targets):
                target_name = (
                    node.targets[0].id if isinstance(node.targets[0], ast.Name) else ""
                )
                if target_name.startswith("_"):
                    if target_name == "_sql_constraints":
                        return "sql_constraint"
                    return "model_attribute"
                return "field"

        elif isinstance(node, ast.FunctionDef):
            return "method"

        elif isinstance(node, ast.ClassDef):
            return "class"

        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            # Docstring
            return "docstring"

        return "unknown"

    def classify_field(
        self,
        node: ast.Assign | ast.AnnAssign,
    ) -> str:
        """
        Classify a field using the rule-based system.

        Args:
            node: AST node of the field

        Returns:
            Field category as string
        """
        field_info = self.get_field_info(node)

        # Check rules in priority order (they're already sorted)
        for rule in self._field_rules:
            if rule.matches(field_info["field_name"], field_info):
                return rule.category

        # This should never happen if rules are complete
        return "UNCATEGORIZED"

    def classify_method(
        self,
        node: ast.FunctionDef,
    ) -> str:
        """
        Classify a method using the rule-based system.

        Args:
            node: AST node of the method

        Returns:
            Method category as string
        """
        method_name = self.get_node_name(node)
        decorators = self.extract_decorators(node)

        # Check rules in priority order (they're already sorted)
        for rule in self._method_rules:
            if rule.matches(method_name, decorators):
                return rule.category

        # This should never happen if rules are complete
        return "UNCATEGORIZED"

    def group_fields_by_category(
        self,
        fields: list[ast.Assign | ast.AnnAssign],
    ) -> dict[str, list]:
        """Group fields by their category based on name and attributes.

        Uses classify_field() to determine each fields's category, then
        groups them into a dictionary.

        Args:
            fields: List of AST ast.Assign or ast.AnnAssign nodes

        Returns:
            dict[str, List]: Dictionary mapping category names to lists of fields
        """
        groups = {}

        for field in fields:
            category = self.classify_field(field)
            # Add to appropriate group
            if category not in groups:
                groups[category] = []
            groups[category].append(field)

        return groups

    def group_methods_by_category(
        self,
        methods: list[ast.FunctionDef],
    ) -> dict[str, list]:
        """Group methods by their category based on name and decorators.

        Uses classify_method() to determine each method's category, then
        groups them into a dictionary.

        Args:
            methods: List of AST FunctionDef nodes

        Returns:
            dict[str, List]: Dictionary mapping category names to lists of methods
        """
        groups = {}

        for method in methods:
            category = self.classify_method(method)
            # Add to appropriate group
            if category not in groups:
                groups[category] = []
            groups[category].append(method)

        return groups

    # ============================================================
    # SORTING FUNCTIONS
    # ============================================================

    def sort_imports(
        self,
        imports: list[str],
    ) -> list[str]:
        """Sort import statements using isort with Odoo conventions.

        Uses isort to organize imports into proper groups with Odoo-specific
        sections (stdlib, third-party, odoo, odoo.addons, relative).

        Args:
            imports: List of import statement strings

        Returns:
            list[str]: Sorted imports with proper grouping and spacing
        """
        if not imports:
            return []

        # Join imports into a single string
        import_str = "\n".join(imports)

        # Use isort to sort with Odoo configuration
        sorted_import_str = isort.code(
            import_str,
            sections=[
                "FUTURE",
                "STDLIB",
                "THIRDPARTY",
                "ODOO",
                "ODOO_ADDONS",
                "FIRSTPARTY",
                "LOCALFOLDER",
            ],
            known_odoo=["odoo", "openerp"],
            known_odoo_addons=["odoo.addons"],
            force_alphabetical_sort_within_sections=True,
            force_sort_within_sections=True,
            lines_between_sections=1,
            multi_line_output=3,
            include_trailing_comma=True,
            force_grid_wrap=0,
            use_parentheses=True,
            ensure_newline_before_comments=True,
            line_length=88,
        )

        # Split back into lines
        return sorted_import_str.split("\n") if sorted_import_str else []

    def sort_model_attributes(
        self,
        attributes: list[str],
        order: list[str],
    ) -> list[str]:
        """Sort Odoo model attributes according to conventions.

        Orders model meta-attributes like _name, _inherit, _description
        in the conventional order used in Odoo models.

        Args:
            attributes: List of attribute assignment strings (e.g., '_name = "model.name"')
            order: Ordered list of attribute names defining sort priority
                (e.g., ['_name', '_inherit', '_description'])

        Returns:
            list[str]: Attributes sorted by the defined order.
                    Unknown attributes get lowest priority.
        """

        def get_attr_priority(attr: str) -> tuple[int, str]:
            # Extract attribute name
            attr_name = attr.split("=")[0].strip()

            try:
                priority = order.index(attr_name)
            except ValueError:
                priority = 99

            return (priority, attr_name)

        return sorted(attributes, key=get_attr_priority)

    def sort_topological(
        self,
        graph: dict[str, list[str]],
    ) -> list[str]:
        """Perform topological sort on a dependency graph.

        Implements Kahn's algorithm for topological sorting, which ensures
        that dependencies come before their dependents. Handles cycles
        gracefully by adding remaining nodes at the end.

        Args:
            graph: Dictionary mapping node names to lists of their dependencies.
                For example: {'A': ['B', 'C'], 'B': ['C']} means A depends on B and C.

        Returns:
            list[str]: Nodes in topologically sorted order. Nodes with no dependencies
                    come first, followed by nodes whose dependencies have been satisfied.
                    Provides stable sorting by sorting the queue at each step.
        """
        # Calculate in-degree for each node
        in_degree = {node: 0 for node in graph}
        for deps in graph.values():
            for dep in deps:
                if dep in in_degree:
                    in_degree[dep] += 1

        # Queue for nodes with no dependencies
        queue = [node for node, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            # Sort queue for stable ordering
            queue.sort()
            node = queue.pop(0)
            result.append(node)

            # Reduce in-degree for dependent nodes
            for dep in graph.get(node, []):
                if dep in in_degree:
                    in_degree[dep] -= 1
                    if in_degree[dep] == 0:
                        queue.append(dep)

        # Add any remaining nodes (cycles or disconnected)
        for node in graph:
            if node not in result:
                result.append(node)

        return result

    def sort_field_attributes(self, node: ast.Assign) -> ast.Assign | None:
        """Reorder attributes in Odoo field declarations using field-type specific ordering.

        Each field type has its own optimal attribute order. For example:
        - Many2one: comodel_name comes first, then string, required, domain, etc.
        - Char: string comes first, then size, required, translate, etc.
        - Selection: selection comes first, then string, required, etc.

        Args:
            node: AST Assign node containing a field declaration

        Returns:
            ast.Assign: Node with reordered field attributes based on field type
        """
        # Detect the field type
        field_type = self.get_field_type(node)
        if not field_type:
            return None

        # Get the appropriate attribute order for this field type
        attribute_order = self.get_field_attribute_order(field_type)

        # Create mapping of attribute names to their positions
        order_map = {attr: i for i, attr in enumerate(attribute_order)}

        # Separate positional args and keyword args
        positional_args = []
        keyword_args = []

        for arg in node.value.args:
            positional_args.append(arg)

        for keyword in node.value.keywords:
            keyword_args.append(keyword)

        # Sort keyword arguments by field-type specific order
        def get_sort_key(keyword):
            if keyword.arg in order_map:
                return (0, order_map[keyword.arg])  # Known attributes in defined order
            else:
                # Unknown attributes go last, sorted alphabetically
                return (1, keyword.arg or "")

        sorted_keywords = sorted(keyword_args, key=get_sort_key)

        # Rebuild the Call node with sorted arguments
        new_call = ast.Call(
            func=node.value.func, args=positional_args, keywords=sorted_keywords
        )

        # Create new Assign node with the reordered call
        new_node = ast.Assign(
            targets=node.targets,
            value=new_call,
            type_comment=getattr(node, "type_comment", None),
        )

        # Copy location info to preserve formatting
        ast.copy_location(new_node, node)
        ast.copy_location(new_call, node.value)

        return new_node

    def sort_methods_with_dependencies(
        self,
        methods: list[dict[str, Any]],
        dependencies: dict[str, list[str]],
    ) -> list[dict[str, Any]]:
        """Sort methods considering their dependency relationships.

        Uses topological sorting to ensure methods that depend on others
        come after their dependencies. Useful for compute methods that
        call other compute methods.

        Args:
            methods: List of method dictionaries, each containing:
                    - 'name': Method name (must match keys in dependencies)
            dependencies: Dictionary mapping method names to lists of methods
                        they depend on

        Returns:
            list[dict[str, Any]]: Methods sorted topologically by dependencies.
                                Methods not in dependency graph are added at the end.
        """
        # Get topological order
        sorted_names = self.sort_topological(dependencies)

        # Create method lookup
        method_lookup = {m.get("name", ""): m for m in methods}

        # Build sorted list
        result = []
        for name in sorted_names:
            if name in method_lookup:
                result.append(method_lookup[name])

        # Add any methods not in dependencies
        for method in methods:
            if method not in result:
                result.append(method)

        return result

    def sort_alphabetical(
        self,
        items: list[Any],
        key_func=None,
    ) -> list[Any]:
        """Perform case-insensitive alphabetical sorting.

        Simple utility for alphabetical sorting with optional key extraction.
        Always uses case-insensitive comparison.

        Args:
            items: List of items to sort
            key_func: Optional function to extract the sort key from each item.
                    If None, items are converted to strings directly.

        Returns:
            list[Any]: Items sorted alphabetically (case-insensitive)
        """
        if key_func:
            return sorted(items, key=lambda x: key_func(x).lower())
        return sorted(items, key=lambda x: str(x).lower())

    # ============================================================
    # HELPERS
    # ============================================================

    def add_method_classification_rule(self, rule: ClassificationRuleMethod):
        """
        Add a custom method classification rule.
        Allows users to extend classification without modifying code.

        Args:
            rule: ClassificationRuleMethod to add
        """
        self._method_rules.append(rule)
        self._method_rules.sort(key=lambda r: r.priority)

    def add_field_classification_rule(self, rule: ClassificationRuleField):
        """
        Add a custom field classification rule.
        Allows users to extend field classification without modifying code.

        Args:
            rule: ClassificationRuleField to add
        """
        self._field_rules.append(rule)
        self._field_rules.sort(key=lambda r: r.priority)

    @staticmethod
    def get_decorator_name(decorator: ast.expr) -> str | None:
        """Extract the name from a decorator node.

        Handles various decorator forms: @name, @module.name, @name(...)

        Args:
            decorator: AST decorator expression

        Returns:
            Optional[str]: Decorator name or None if not extractable
        """
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            return decorator.attr
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name):
                return decorator.func.id
            elif isinstance(decorator.func, ast.Attribute):
                return decorator.func.attr
        return None

    def get_field_attribute_order(self, field_type: str) -> list[str]:
        """Get the optimal attribute order for a specific field type.

        Args:
            field_type: The Odoo field type (e.g., 'Char', 'Many2one')

        Returns:
            list[str]: Ordered list of attribute names for this field type
        """
        # Check if we have specific ordering for this field type
        if field_type in self.FIELD_TYPE_ATTRIBUTES:
            return self.FIELD_TYPE_ATTRIBUTES[field_type]

        # Fall back to generic ordering
        return self.FIELD_ATTRIBUTE_GENERIC

    def get_field_info(
        self,
        node: ast.Assign | ast.AnnAssign,
    ) -> dict[str, Any]:
        """
        Extract field information from an AST node.

        Args:
            node: AST node representing a field assignment

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

        info["field_name"] = self.get_node_name(node)

        if isinstance(node, ast.Assign):
            info["field_type"] = self.get_field_type(node)
            # Get field attributes
            if node.value and isinstance(node.value, ast.Call):
                # Check for special attributes
                for keyword in node.value.keywords:
                    if keyword.arg == "compute":
                        info["is_computed"] = True
                    if keyword.arg == "related":
                        info["is_related"] = True

                        related_path = None
                        if isinstance(keyword.value, ast.Constant):
                            related_path = keyword.value.value
                        # Extract the base field (first part before '.')
                        if related_path and "." in related_path:
                            info["related_field_base"] = related_path.split(".")[0]
                        elif related_path:
                            info["related_field_base"] = related_path

        return info

    def get_field_type(self, node: ast.Assign) -> str | None:
        """Detect the Odoo field type from an AST node.

        Args:
            node: AST Assign node containing a field declaration

        Returns:
            str: Field type name (e.g., 'Char', 'Many2one') or None if not a field
        """
        if not isinstance(node.value, ast.Call):
            return None

        if not (
            isinstance(node.value.func, ast.Attribute)
            and isinstance(node.value.func.value, ast.Name)
            and node.value.func.value.id == "fields"
        ):
            return None

        # Extract field type from fields.FieldType
        return node.value.func.attr

    def get_line_range(self, node: ast.AST) -> tuple[int, int]:
        """Get the line range for an AST node.

        Args:
            node: AST node to get line range for

        Returns:
            Tuple[int, int]: (start_line, end_line) or (0, 0) if not available
        """
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            return (node.lineno, node.end_lineno or node.lineno)
        elif hasattr(node, "lineno"):
            return (node.lineno, node.lineno)
        return (0, 0)

    @staticmethod
    def get_node_name(node: ast.AST) -> str | None:
        """Extract the identifying name from various AST node types.

        Handles different node types:
        - Nodes with 'name' attribute (ClassDef, FunctionDef)
        - Assignment nodes (extracts target names)
        - Annotated assignments

        Args:
            node: AST node to get name from

        Returns:
            Optional[str]: The node's name or None if not applicable
        """
        if hasattr(node, "name"):
            return node.name
        if isinstance(node, ast.Assign):
            targets = []
            for target in node.targets:
                if isinstance(target, ast.Name):
                    targets.append(target.id)
                elif isinstance(target, ast.Tuple):
                    for elt in target.elts:
                        if isinstance(elt, ast.Name):
                            targets.append(elt.id)
            return ", ".join(targets) if targets else None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            return node.target.id
        return None

    def _is_property(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """Check if a function is decorated as a property.

        Args:
            node: Function definition to check

        Returns:
            bool: True if the function has a property decorator
        """
        for decorator in node.decorator_list:
            decorator_name = self.get_decorator_name(decorator)
            if decorator_name and "property" in decorator_name:
                return True
        return False

    # ============================================================
    # REORGANIZER
    # ============================================================

    def unparse_node(
        self,
        node: ast.AST,
        indent: str = "",
        prefix: str = "",
    ) -> str:
        """Convert an AST node back to Python source code.

        Args:
            node: AST node to unparse
            indent: String to prepend to each line for indentation
            prefix: String to prepend to the result (e.g., '@' for decorators)

        Returns:
            str: Python source code representation of the node, with indentation
                and prefix applied. Returns placeholder comment if unparsing fails.
        """
        try:
            unparsed = ast.unparse(node)
            if prefix:
                unparsed = prefix + unparsed.lstrip("@")
            if indent:
                # Add indent to each line
                lines = unparsed.split("\n")
                unparsed = "\n".join(indent + line if line else line for line in lines)
            return unparsed
        except Exception as e:
            logger.debug(f"Failed to unparse node: {e}")
            return f"{indent}# [unparseable node]"

    def reorganize_class(self, class_node: ast.ClassDef) -> list[str]:
        """Reorganize a class definition into properly ordered sections.

        Uses ASTProcessor to extract class elements, then rebuilds
        the class with proper ordering and optional section headers.

        Args:
            class_node: AST ClassDef node to reorganize

        Returns:
            list[str]: Lines of reorganized class code
        """
        lines = []

        # Extract all class elements
        elements = self.extract_class_elements(class_node)

        # Build class body

        # Class definition
        for decorator in elements["decorators"]:
            lines.append(self.unparse_node(decorator, prefix="@"))

        class_bases = [ast.unparse(base) for base in elements["class_bases"]]
        class_bases = ", ".join(class_bases)
        lines.append(f"class {class_node.name}({class_bases}):")

        # Docstring
        if elements["docstring"]:
            lines.append(self.unparse_node(elements["docstring"][0], indent="    "))
            lines.append("")

        # Model attributes
        if elements["model_attrs"]:
            for attr in elements["model_attrs"]:
                lines.append(self.unparse_node(attr, indent="    "))
            lines.append("")

        # Class variables
        if elements["class_vars"]:
            for attr in elements["class_vars"]:
                lines.append(self.unparse_node(attr, indent="    "))
            lines.append("")

        # Class properties
        if elements["properties"]:
            for attr in elements["properties"]:
                lines.append(self.unparse_node(attr, indent="    "))
            lines.append("")

        # Fields section
        if elements["fields"]:
            if self.config.add_section_headers:
                lines.extend(format_section_header("FIELDS"))

            for field in elements["fields"]:
                lines.append(self.unparse_node(field, indent="    "))
            lines.append("")

        # Methods section
        if elements["methods"]:
            # Define the standard Odoo method order
            method_order = [
                "CONSTRAINT",
                "CRUD",
                "COMPUTE",
                "INVERSE",
                "SEARCH",
                "ONCHANGE",
                "WORKFLOW",
                "ACTIONS",
                "PREPARE",
                "GETTER",
                "REPORT",
                "IMPORT_EXPORT",
                "SECURITY",
                "PORTAL",
                "COMMUNICATION",
                "WIZARD",
                "INTEGRATION",
                "CRON",
                "ACCOUNTING",
                "MANUFACTURING",
                "PRODUCT_CATALOG",
                "MAIL_THREAD",
                "OVERRIDE",
                "API_MODEL",
                "PUBLIC",
                "PRIVATE",
            ]

            # Output methods in the defined order
            for category in method_order:
                if category in elements["methods"]:
                    if self.config.add_section_headers:
                        lines.extend(format_section_header(f"{category} METHODS"))

                    for method in elements["methods"][category]:
                        # Decorators are included in the method unparsing, no need to add separately
                        lines.append(self.unparse_node(method, indent="    "))
                        lines.append("")

        return lines

    def reorganize_content(self, tree: ast.Module) -> str:
        """Reorganize entire module content.

        Extracts all elements, then rebuilds the module with proper
        ordering and spacing.

        Args:
            tree: Parsed AST Module node

        Returns:
            str: Reorganized Python source code
        """
        result_lines = []

        # Set the tree for extraction
        self.set_tree(tree)

        # Extract all elements
        module_elements = self.extract_elements()

        # Build output

        # Module docstring - use ast.get_docstring to check, then get the node
        if ast.get_docstring(tree):
            for node in tree.body:
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                    result_lines.append(self.unparse_node(node))
                    result_lines.append("")
                    break

        # Imports
        if module_elements["imports"]:
            import_strs = [self.unparse_node(imp) for imp in module_elements["imports"]]
            sorted_imports = self.sort_imports(import_strs)
            result_lines.extend(sorted_imports)
            result_lines.append("")

        # Module variables
        for var in module_elements["module_vars"]:
            result_lines.append(self.unparse_node(var))
            result_lines.append("")

        # Module functions
        for func in module_elements["functions"]:
            result_lines.append(self.unparse_node(func))
            result_lines.append("")

        # Classes
        for class_node in module_elements["classes"]:
            class_lines = self.reorganize_class(class_node)
            result_lines.extend(class_lines)
            result_lines.append("")

        return "\n".join(result_lines)
