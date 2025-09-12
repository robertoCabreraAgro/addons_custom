#!/usr/bin/env python3
"""
Odoo Source Code Reorganizer with Black Formatting - Version 2
Now using shared components for improved efficiency and maintainability.

This tool reorganizes and formats Odoo Python source files for consistency.
Supports Odoo versions 17.0, 18.0, and 19.0.

Author: Agromarin Tools
Version: 2.0.0
"""

import argparse
import ast
import logging
import sys
import traceback

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Import shared components
from core import (
    BaseASTProcessor,
    ElementExtractor,
    ElementType,
    FileOperations,
    SharedCache,
    UnifiedElement,
)
from core.classifiers import (
    FieldClassifier as CoreFieldClassifier,
    MethodClassifier as CoreMethodClassifier,
    ModelElementClassifier,
)
from core.sorting_utils import (
    TopologicalSorter,
    FieldSorter,
    MethodSorter,
    AlphabeticalSorter,
)
from config import (
    ConfigManager,
    OdooConfig,
    ReorderConfig,
)

# Third-party imports
try:
    import black
except ImportError:
    print("Error: Black is not installed. Please install it with: pip install black")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES FOR ORDER EXPORT/IMPORT
# =============================================================================


class OrderExportType(Enum):
    """Type of order export."""

    FILE = auto()
    MODULE = auto()
    DIRECTORY = auto()


@dataclass
class ClassOrder:
    """Represents the order of elements in a class."""

    name: str
    model_attributes: List[str] = field(default_factory=list)
    fields: List[str] = field(default_factory=list)
    sql_constraints: List[str] = field(default_factory=list)
    model_indexes: List[str] = field(default_factory=list)
    methods: Dict[str, List[str]] = field(default_factory=dict)
    section_headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class FileOrder:
    """Represents the order of elements in a file."""

    filepath: str
    import_groups: List[str] = field(default_factory=list)
    import_statements: List[str] = field(default_factory=list)
    classes: List[ClassOrder] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    module_level_vars: List[str] = field(default_factory=list)


@dataclass
class OrderExport:
    """Complete order export data."""

    version: str = "1.0"
    odoo_version: str = "19.0"
    export_date: str = field(default_factory=lambda: datetime.now().isoformat())
    export_type: OrderExportType = OrderExportType.FILE
    name: str = ""
    files: Dict[str, FileOrder] = field(default_factory=dict)


# =============================================================================
# IMPORT ORGANIZER
# =============================================================================


class ImportOrganizer:
    """Organizes imports according to Odoo conventions."""

    def __init__(self, odoo_config: Optional[OdooConfig] = None):
        self.odoo_config = odoo_config or OdooConfig.get_default()
        self.cache = SharedCache()
        self._stdlib_modules = None

    def organize_imports(
        self, imports: List[ast.stmt], processor: BaseASTProcessor
    ) -> Dict[str, List[ast.stmt]]:
        """Organize imports into groups."""
        groups = {
            "python_stdlib": [],
            "third_party": [],
            "odoo": [],
            "odoo_addons": [],
            "relative": [],
        }

        for import_node in imports:
            group = self._classify_import(import_node)
            groups[group].append(import_node)

        # Sort imports within each group
        for group in groups:
            groups[group] = sorted(
                groups[group], key=lambda x: processor.safe_unparse(x).lower()
            )

        return groups

    def _classify_import(self, import_node: ast.stmt) -> str:
        """Classify an import into its appropriate group."""
        if isinstance(import_node, ast.ImportFrom):
            if import_node.level > 0:  # Relative import
                return "relative"
            module = import_node.module or ""
        else:
            module = import_node.names[0].name

        # Check patterns
        if self._is_odoo_addon(module):
            return "odoo_addons"
        elif self._is_odoo_import(module):
            return "odoo"
        elif self._is_stdlib(module):
            return "python_stdlib"
        else:
            return "third_party"

    def _is_odoo_import(self, module: str) -> bool:
        """Check if module is an Odoo core import."""
        return any(
            module.startswith(pattern)
            for pattern in self.odoo_config.import_patterns["odoo"]
        )

    def _is_odoo_addon(self, module: str) -> bool:
        """Check if module is an Odoo addon import."""
        return any(
            module.startswith(pattern)
            for pattern in self.odoo_config.import_patterns["odoo_addons"]
        )

    def _is_stdlib(self, module: str) -> bool:
        """Check if module is a Python standard library module."""
        if self._stdlib_modules is None:
            import sys

            self._stdlib_modules = set(sys.stdlib_module_names)

        base_module = module.split(".")[0]
        return base_module in self._stdlib_modules


# =============================================================================
# CODE REORGANIZER
# =============================================================================


class CodeReorganizer:
    """Main class for reorganizing Odoo code.

    Model attributes and methods always follow rigid ordering.
    Field ordering strategy can be customized.
    """

    def __init__(
        self,
        odoo_config: Optional[OdooConfig] = None,
        reorder_config: Optional[ReorderConfig] = None,
        field_strategy: str = "semantic",  # "semantic", "type", or "strict"
    ):
        self.odoo_config = odoo_config or OdooConfig.get_default()
        self.reorder_config = reorder_config or ReorderConfig.get_default()
        self.field_strategy = field_strategy
        self.file_ops = FileOperations()
        self.cache = SharedCache()
        self.import_organizer = ImportOrganizer(odoo_config)

        # Field strategy determines how fields are grouped and ordered
        self.field_classifier = CoreFieldClassifier(strategy=field_strategy)

        # Methods always use rigid ordering (no semantic grouping)
        self.method_classifier = CoreMethodClassifier()

    def reorganize_file(self, filepath: Path) -> Tuple[str, bool]:
        """
        Reorganize a Python file.

        Returns:
            Tuple of (new_content, changed)
        """
        logger.info(f"Processing {filepath}")

        # Read file
        content = self.file_ops.read_file(filepath)

        # Parse AST
        processor = BaseASTProcessor(content, filepath)
        extractor = ElementExtractor(processor)

        # Extract elements
        elements = extractor.extract_all(include_source=True)

        # Reorganize
        new_content = self._reorganize_content(processor, elements)

        # Format with Black if configured
        if self.reorder_config.use_black:
            try:
                mode = black.Mode(
                    line_length=self.reorder_config.line_length,
                    string_normalization=self.reorder_config.string_normalization,
                    magic_trailing_comma=self.reorder_config.magic_trailing_comma,
                )
                new_content = black.format_str(new_content, mode=mode)
            except Exception as e:
                logger.warning(f"Black formatting failed: {e}")

        changed = new_content != content
        return new_content, changed

    def _reorganize_content(
        self,
        processor: BaseASTProcessor,
        elements: Dict[ElementType, List[UnifiedElement]],
    ) -> str:
        """Reorganize the content based on extracted elements."""
        lines = []

        # Add header comments
        header_lines = self._extract_header(processor)
        if header_lines:
            lines.extend(header_lines)
            lines.append("")

        # Add imports
        imports = processor.extract_imports()
        if imports:
            organized_imports = self.import_organizer.organize_imports(
                imports, processor
            )
            for group in self.reorder_config.import_group_order:
                group_imports = organized_imports.get(group, [])
                if group_imports:
                    if lines and lines[-1] != "":
                        lines.append("")
                    for imp in group_imports:
                        lines.append(processor.safe_unparse(imp))
            lines.append("")

        # Add module-level variables
        module_vars = elements.get(ElementType.MODULE_VAR, [])
        if module_vars:
            lines.append("")
            for var in module_vars:
                if var.source:
                    lines.append(var.source)
            lines.append("")

        # Add classes
        classes = elements.get(ElementType.CLASS, [])
        for class_elem in classes:
            lines.append("")
            lines.extend(self._reorganize_class(class_elem, processor))

        # Add functions
        functions = elements.get(ElementType.FUNCTION, [])
        functions.extend(elements.get(ElementType.ASYNC_FUNCTION, []))
        if functions:
            lines.append("")
            for func in functions:
                if func.source:
                    lines.append(func.source)
                    lines.append("")

        return "\n".join(lines)

    def _reorganize_class(
        self, class_elem: UnifiedElement, processor: BaseASTProcessor
    ) -> List[str]:
        """Reorganize a class definition."""
        lines = []

        # Class definition
        if class_elem.node:
            # Get class header (definition + decorators)
            class_def = processor.safe_unparse(class_elem.node)
            # We'll rebuild the class body
            class_lines = class_def.split("\n")

            # Find where the body starts
            for i, line in enumerate(class_lines):
                if line.strip().endswith(":"):
                    lines.extend(class_lines[: i + 1])
                    break

        # Get class elements
        class_node = class_elem.node
        if not isinstance(class_node, ast.ClassDef):
            return lines

        # Extract class elements
        class_elements = processor.extract_class_elements(class_node)

        # FIRST: Add docstring if present (immediately after class definition)
        docstring = processor.get_docstring(class_node)
        if docstring:
            lines.append(f'    """{docstring}"""')
            lines.append("")

        # SECOND: Add model attributes (no section header - they go after docstring)
        model_attrs = self._get_model_attributes(class_node, processor)
        if model_attrs:
            for attr in model_attrs:
                lines.append(f"    {attr}")
            lines.append("")

        # Fields (filter out model attributes and constraints)
        fields = class_elements.get("fields", [])
        # Filter out model attributes and model constraints
        filtered_fields = []
        for field_node in fields:
            if isinstance(field_node, ast.Assign):
                skip_field = False
                for target in field_node.targets:
                    if isinstance(target, ast.Name):
                        # Skip if it's a model attribute
                        if self.odoo_config.is_model_attribute(target.id):
                            skip_field = True
                            break
                        # Skip _sql_constraints
                        if target.id == "_sql_constraints":
                            skip_field = True
                            break
                        # Skip models.Constraint and models.Index fields
                        field_source = processor.safe_unparse(field_node)
                        if "models.Constraint" in field_source:
                            skip_field = True
                            break
                        # Skip model indexes
                        if ModelElementClassifier.is_model_index(
                            target.id, field_source
                        ):
                            skip_field = True
                            break
                if not skip_field:
                    filtered_fields.append(field_node)
            else:
                filtered_fields.append(field_node)

        if filtered_fields:
            if self.field_strategy == "semantic":
                # Semantic field grouping - group by meaning, then sort within groups
                field_groups = self._group_fields_semantically(
                    filtered_fields, processor
                )
                field_order = [
                    "IDENTIFIERS",
                    "ATTRIBUTES",
                    "GENEALOGY",
                    "RELATIONSHIPS",
                    "MEASURES",
                    "DATES",
                    "CONTENT",
                    "COMPUTED",
                ]

                for group_name in field_order:
                    if group_name in field_groups and field_groups[group_name]:
                        if self.reorder_config.add_section_headers:
                            lines.extend(
                                self._get_section_header(f"{group_name} FIELDS").split(
                                    "\n"
                                )
                            )
                            lines.append("")  # Add empty line after header

                        # Sort fields within group
                        if group_name == "GENEALOGY":
                            # Use specific ordering for genealogy fields
                            group_fields = FieldSorter.sort_genealogy(
                                field_groups[group_name], self._get_field_name_from_node
                            )
                        elif group_name == "RELATIONSHIPS":
                            # Use special sorting for relationship fields
                            group_fields = FieldSorter.sort_relationship(
                                field_groups[group_name],
                                self._get_field_name_from_node,
                                lambda node: self._get_field_type_from_node(
                                    node, processor
                                ),
                            )
                        elif group_name == "ATTRIBUTES":
                            # Sort ATTRIBUTES fields alphabetically
                            group_fields = FieldSorter.sort_alphabetically(
                                field_groups[group_name], self._get_field_name_from_node
                            )
                        else:
                            # Sort all other fields by type and name
                            group_fields = FieldSorter.sort_by_type_and_name(
                                field_groups[group_name],
                                self._get_field_name_from_node,
                                lambda node: self._get_field_type_from_node(
                                    node, processor
                                ),
                            )

                        # Final step: Always ensure related fields are next to their base fields
                        group_fields = FieldSorter.organize_with_related(
                            group_fields,
                            self._get_field_name_from_node,
                            lambda node: self.field_classifier.extract_field_info(node),
                        )

                        for field_node in group_fields:
                            field_source = processor.get_source_segment(field_node)
                            if field_source:
                                for line in field_source.split("\n"):
                                    lines.append(f"    {line}")
                        lines.append("")

            elif self.field_strategy == "type":
                # Group by field type only, no semantic grouping
                if self.reorder_config.add_section_headers:
                    lines.extend(self._get_section_header("FIELDS").split("\n"))
                    lines.append("")  # Add empty line after header

                # Sort all fields by type then alphabetically
                sorted_fields = FieldSorter.sort_by_type_and_name(
                    filtered_fields,
                    self._get_field_name_from_node,
                    lambda node: self._get_field_type_from_node(node, processor),
                )
                for field_node in sorted_fields:
                    field_source = processor.get_source_segment(field_node)
                    if field_source:
                        for line in field_source.split("\n"):
                            lines.append(f"    {line}")
                lines.append("")

            else:  # field_strategy == "strict"
                # Strict ordering - AgroMarin rigid field type order
                if self.reorder_config.add_section_headers:
                    lines.extend(self._get_section_header("FIELDS").split("\n"))
                    lines.append("")  # Add empty line after header

                # Sort by strict type order from AgroMarin standards
                sorted_fields = FieldSorter.sort_strict(
                    filtered_fields,
                    self._get_field_name_from_node,
                    lambda node: self._get_field_type_from_node(node, processor),
                    lambda node: self.field_classifier.extract_field_info(node).get(
                        "is_computed", False
                    ),
                )
                for field_node in sorted_fields:
                    field_source = processor.get_source_segment(field_node)
                    if field_source:
                        for line in field_source.split("\n"):
                            lines.append(f"    {line}")
                lines.append("")

        # Model Constraints (models.Constraint fields)
        model_constraints = self._get_model_constraints(class_node, processor)
        if model_constraints:
            if self.reorder_config.add_section_headers:
                lines.extend(self._get_section_header("MODEL CONSTRAINTS").split("\n"))
                lines.append("")  # Add empty line after header
            for constraint in model_constraints:
                lines.append(f"    {constraint}")
            lines.append("")

        # SQL Constraints
        sql_constraints = self._get_model_sql_constraints(class_node, processor)
        if sql_constraints:
            if self.reorder_config.add_section_headers:
                lines.extend(self._get_section_header("SQL CONSTRAINTS").split("\n"))
                lines.append("")  # Add empty line after header
            for constraint in sql_constraints:
                lines.append(f"    {constraint}")
            lines.append("")

        # Model Indexes (only show if not already in fields section)
        model_indexes = self._get_model_indexes(class_node, processor)
        # Get field names to check for duplicates (from filtered fields, not all fields)
        field_names = set()
        for field_node in filtered_fields:
            if isinstance(field_node, ast.Assign):
                for target in field_node.targets:
                    if isinstance(target, ast.Name):
                        field_names.add(target.id)

        # Only include indexes that aren't already shown as fields
        unique_indexes = []
        for index in model_indexes:
            # Parse the index assignment to get its name
            try:
                index_ast = ast.parse(index).body[0]
                if isinstance(index_ast, ast.Assign):
                    for target in index_ast.targets:
                        if (
                            isinstance(target, ast.Name)
                            and target.id not in field_names
                        ):
                            unique_indexes.append(index)
            except:
                # If we can't parse it, include it to be safe
                unique_indexes.append(index)

        if unique_indexes:
            if self.reorder_config.add_section_headers:
                lines.extend(self._get_section_header("MODEL INDEXES").split("\n"))
                lines.append("")  # Add empty line after header
            for index in unique_indexes:
                lines.append(f"    {index}")
            lines.append("")

        # Methods by category
        methods = class_elements.get("methods", [])
        method_categories = self._categorize_methods(methods, processor)

        # Rigid method ordering (always the same order)
        category_order = [
            "CONSTRAINTS",
            "CRUD",
            "COMPUTE",
            "INVERSE",
            "SEARCH",
            "ONCHANGE",
            "ACTION",
            "API_MODEL",
            "PUBLIC",
            "PRIVATE",
        ]

        for category in category_order:
            category_methods = method_categories.get(category, [])
            if category_methods:
                if self.reorder_config.add_section_headers:
                    if category == "ACTION":
                        header_title = "ACTION METHODS"
                    elif category == "API_MODEL":
                        header_title = "API MODEL METHODS"
                    else:
                        header_title = f"{category} METHODS"
                    lines.extend(self._get_section_header(header_title).split("\n"))
                    lines.append("")  # Add empty line after header

                # Sort methods within category based on category type
                if category == "CRUD":
                    sorted_methods = MethodSorter.sort_crud_methods(category_methods)
                elif category == "COMPUTE":
                    # Build dependency graph for compute methods
                    dependency_graph = MethodSorter._build_dependency_graph(
                        category_methods, processor
                    )
                    sorted_methods = MethodSorter.sort_topological_methods(
                        category_methods, dependency_graph
                    )
                elif category == "ONCHANGE":
                    # Build dependency graph for onchange methods
                    dependency_graph = MethodSorter._build_dependency_graph(
                        category_methods, processor
                    )
                    sorted_methods = MethodSorter.sort_topological_methods(
                        category_methods, dependency_graph
                    )
                elif category in ["INVERSE", "SEARCH", "ACTION"]:
                    # Explicitly sort these categories alphabetically
                    sorted_methods = sorted(
                        category_methods, key=lambda m: m.name.lower()
                    )
                else:
                    # Sort methods within category alphabetically
                    sorted_methods = sorted(
                        category_methods, key=lambda m: m.name.lower()
                    )

                for method in sorted_methods:
                    # Get decorators first
                    if hasattr(method, "decorator_list") and method.decorator_list:
                        for decorator in method.decorator_list:
                            lines.append(
                                f"    {processor.get_decorator_source(decorator)}"
                            )

                    # Then get the method source
                    method_source = processor.get_source_segment(method)
                    if method_source:
                        for line in method_source.split("\n"):
                            lines.append(f"    {line}")
                        lines.append("")

        return lines

    def _categorize_methods(
        self, methods: List[ast.AST], processor: BaseASTProcessor
    ) -> Dict[str, List[ast.AST]]:
        """Categorize methods by type."""
        categories = {}

        for method in methods:
            if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                category = self.method_classifier.classify_method_node(method)
                if category not in categories:
                    categories[category] = []
                categories[category].append(method)

        return categories

    def _get_model_attributes(
        self, class_node: ast.ClassDef, processor: BaseASTProcessor
    ) -> List[str]:
        """Extract model attributes from a class."""
        attributes = []
        # Define the order for model attributes
        model_attr_order = [
            "_name",
            "_inherits",
            "_inherit",
            "_description",
            "_table",
            "_table_query",
            "_sequence",  # deprecated but might be in legacy code
            "_active_name",
            "_date_name",
            "_fold_name",
            "_parent_name",
            "_parent_store",
            "_parent_order",  # not in 19.0 but keep for compatibility
            "_rec_name",
            "_rec_names_search",
            "_auto",
            "_abstract",
            "_check_company_auto",
            "_check_company_domain",
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
        ]

        # First pass: collect all model attributes
        attr_dict = {}
        for node in class_node.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        source = processor.safe_unparse(node)
                        # Use the classifier to determine if it's a model attribute
                        if ModelElementClassifier.is_model_attribute(target.id, source):
                            attr_dict[target.id] = source

        # Second pass: add in proper order
        for attr_name in model_attr_order:
            if attr_name in attr_dict:
                attributes.append(attr_dict[attr_name])

        # Add any remaining model attributes not in our order list
        for attr_name, attr_value in attr_dict.items():
            if attr_name not in model_attr_order and attr_value not in attributes:
                attributes.append(attr_value)

        return attributes

    def _get_model_indexes(
        self, class_node: ast.ClassDef, processor: BaseASTProcessor
    ) -> List[str]:
        """Extract model indexes from a class."""
        indexes = []
        for node in class_node.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        source = processor.safe_unparse(node)
                        # Use the classifier to determine if it's a model index
                        if ModelElementClassifier.is_model_index(target.id, source):
                            indexes.append(source)
        return indexes

    def _get_model_sql_constraints(
        self, class_node: ast.ClassDef, processor: BaseASTProcessor
    ) -> List[str]:
        """Extract SQL constraints from a class."""
        constraints = []

        for node in class_node.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "_sql_constraints":
                        constraints.append(processor.safe_unparse(node))

        return constraints

    def _get_model_constraints(
        self, class_node: ast.ClassDef, processor: BaseASTProcessor
    ) -> List[str]:
        """Extract model constraints (models.Constraint fields) from a class."""
        constraints = []

        for node in class_node.body:
            if isinstance(node, ast.Assign):
                # Check if it's a models.Constraint field
                if isinstance(node.value, ast.Call):
                    call_str = processor.safe_unparse(node.value)
                    if "models.Constraint" in call_str:
                        constraints.append(processor.safe_unparse(node))

        return constraints

    def _get_section_header(self, title: str) -> str:
        """Generate a section header."""
        if not self.reorder_config.add_section_headers:
            return ""

        separator = self.reorder_config.section_separator
        return self.reorder_config.section_header_format.format(
            separator=separator, title=title
        )

    def _get_field_name_from_node(self, field_node: ast.AST) -> Optional[str]:
        """Get field name from an AST node."""
        if isinstance(field_node, ast.Assign):
            for target in field_node.targets:
                if isinstance(target, ast.Name):
                    return target.id
        return None

    def _get_field_type_from_node(
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

    def _extract_header(self, processor: BaseASTProcessor) -> List[str]:
        """Extract header comments from file."""
        header = []

        for line in processor.lines:
            if any(
                pattern in line.lower() for pattern in self.odoo_config.header_patterns
            ):
                header.append(line)
            elif line.strip() and not line.strip().startswith("#"):
                break
            elif line.strip().startswith("#"):
                header.append(line)

        return header

    def _group_fields_semantically(
        self, fields: List[ast.AST], processor: BaseASTProcessor
    ) -> Dict[str, List[ast.AST]]:
        """Group fields by semantic meaning, keeping related fields with their base fields."""
        groups = defaultdict(list)
        field_to_group = {}  # Map field name to its semantic group
        related_field_info = {}  # Map related field to its base field

        # First pass: classify all fields and track related fields
        for field_node in fields:
            if isinstance(field_node, ast.Assign) and field_node.targets:
                target = field_node.targets[0]
                if isinstance(target, ast.Name):
                    field_name = target.id
                    # Skip model attributes (they're handled separately)
                    if field_name.startswith("_"):
                        continue

                    # Check if it's a related field
                    base_field = self.field_classifier.get_related_field_base(
                        field_node
                    )
                    if base_field:
                        related_field_info[field_name] = base_field

                    # Classify the field normally
                    category = self.field_classifier.classify_field_node(field_node)
                    if category:
                        field_to_group[field_name] = category
                        groups[category].append(field_node)

        # Second pass: move related fields to their base field's group if different
        for related_field, base_field in related_field_info.items():
            if base_field in field_to_group:
                base_group = field_to_group[base_field]
                related_group = field_to_group.get(related_field)

                # If the related field is in a different group, move it
                if related_group and related_group != base_group:
                    # Find and remove the field from its current group
                    for field_node in groups[related_group][:]:
                        if isinstance(field_node, ast.Assign) and field_node.targets:
                            target = field_node.targets[0]
                            if (
                                isinstance(target, ast.Name)
                                and target.id == related_field
                            ):
                                groups[related_group].remove(field_node)
                                groups[base_group].append(field_node)
                                field_to_group[related_field] = base_group
                                break

        return groups


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser."""
    parser = argparse.ArgumentParser(
        description="Reorganize Odoo source code (v2 - using shared components)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "path",
        help="File, directory, or module to process",
    )
    parser.add_argument(
        "--field-strategy",
        choices=["semantic", "type", "strict"],
        default="semantic",
        help="Field ordering strategy: 'semantic' (default - groups by meaning), 'type' (group by field type), 'strict' (AgroMarin rigid order)",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Process directories recursively",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create backup files",
    )
    parser.add_argument(
        "--keep-backups",
        action="store_true",
        help="Keep backup files after processing (default: delete them)",
    )
    parser.add_argument(
        "-l",
        "--line-length",
        type=int,
        default=88,
        help="Line length for Black formatting (default: 88)",
    )
    parser.add_argument(
        "--odoo-version",
        default="19.0",
        choices=["17.0", "18.0", "19.0"],
        help="Odoo version (default: 19.0)",
    )
    parser.add_argument(
        "--export-order",
        action="store_true",
        help="Export the code organization pattern",
    )
    parser.add_argument(
        "--apply-order",
        type=str,
        help="Apply ordering from a JSON file",
    )
    parser.add_argument(
        "-o",
        "--order-output",
        default="order.json",
        help="Output file for order export (default: order.json)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    return parser


def main():
    """Main entry point."""
    parser = create_argument_parser()
    args = parser.parse_args()

    # Setup logging
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Setup configuration
    odoo_config = OdooConfig.get_default()
    odoo_config.version = args.odoo_version

    reorder_config = ReorderConfig.get_default()
    reorder_config.line_length = args.line_length
    reorder_config.dry_run = args.dry_run
    reorder_config.create_backup = not args.no_backup

    # Register configs
    ConfigManager.register_config("odoo", OdooConfig)
    ConfigManager.register_config("reorder", ReorderConfig)
    ConfigManager.set_config("odoo", odoo_config)
    ConfigManager.set_config("reorder", reorder_config)

    try:
        path = Path(args.path)

        if not path.exists():
            logger.error(f"Path does not exist: {path}")
            sys.exit(1)

        # Handle order export
        if args.export_order:
            exporter = OrderExporter()

            if path.is_file():
                order_data = exporter.export_file(path, args.odoo_version)
            else:
                logger.error("Export only supports single files currently")
                sys.exit(1)

            output_path = Path(args.order_output)
            exporter.save_order(order_data, output_path)
            logger.info(f"Order exported to {output_path}")

        # Handle order import
        elif args.apply_order:
            importer = OrderImporter()
            order_file = Path(args.apply_order)
            file_ops = FileOperations()

            if not order_file.exists():
                logger.error(f"Order file not found: {order_file}")
                sys.exit(1)

            order_data = importer.load_order(order_file)

            if path.is_file():
                new_content, changed = importer.apply_order_to_file(order_data, path)

                if changed and not args.dry_run:
                    if not args.no_backup:
                        file_ops.create_backup(path)
                    file_ops.write_file(path, new_content)
                    logger.info(f"Applied order to {path}")
                elif changed:
                    logger.info(f"Would apply order to {path}")
                else:
                    logger.info(f"No changes needed for {path}")

                # Clean up backup files unless --keep-backups is specified
                if not args.dry_run and not args.no_backup and not args.keep_backups:
                    file_ops.cleanup_backups()
                    logger.info("Cleaned up backup files")
            else:
                logger.error("Apply order only supports single files currently")
                sys.exit(1)

        # Regular reorganization
        else:
            reorganizer = CodeReorganizer(
                odoo_config,
                reorder_config,
                field_strategy=args.field_strategy,
            )
            file_ops = FileOperations()

            if path.is_file():
                new_content, changed = reorganizer.reorganize_file(path)

                if changed and not args.dry_run:
                    if not args.no_backup:
                        file_ops.create_backup(path)
                    file_ops.write_file(path, new_content)
                    logger.info(f"Reorganized {path}")
                elif changed:
                    logger.info(f"Would reorganize {path}")
                else:
                    logger.info(f"No changes needed for {path}")
            else:
                # Directory processing
                pattern = "**/*.py" if args.recursive else "*.py"

                for py_file in path.glob(pattern):
                    if file_ops.should_skip(py_file, odoo_config.skip_dirs):
                        continue

                    new_content, changed = reorganizer.reorganize_file(py_file)

                    if changed and not args.dry_run:
                        if not args.no_backup:
                            file_ops.create_backup(py_file)
                        file_ops.write_file(py_file, new_content)
                        logger.info(f"Reorganized {py_file}")
                    elif changed:
                        logger.info(f"Would reorganize {py_file}")

            # Clean up backup files unless --keep-backups is specified
            if not args.dry_run and not args.no_backup and not args.keep_backups:
                file_ops.cleanup_backups()
                logger.info("Cleaned up backup files")

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
