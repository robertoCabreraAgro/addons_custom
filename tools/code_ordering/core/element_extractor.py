"""
Unified element extraction for consistent AST analysis.

This module provides a unified way to extract and represent
code elements across all tools.
"""

import ast
import logging

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Union

from .ast_processor import BaseASTProcessor

logger = logging.getLogger(__name__)


class ElementType(Enum):
    """Types of code elements."""

    MODULE = auto()
    IMPORT = auto()
    IMPORT_FROM = auto()
    CLASS = auto()
    FUNCTION = auto()
    ASYNC_FUNCTION = auto()
    METHOD = auto()
    ASYNC_METHOD = auto()
    PROPERTY = auto()
    FIELD = auto()
    CLASS_VAR = auto()
    MODULE_VAR = auto()
    DECORATOR = auto()
    DOCSTRING = auto()
    COMMENT = auto()
    SQL_CONSTRAINT = auto()
    MODEL_INDEX = auto()


@dataclass
class UnifiedElement:
    """
    Unified representation of a code element.

    This class provides a consistent interface for all code elements,
    reducing duplication and improving maintainability.
    """

    name: str
    type: ElementType
    node: Optional[ast.AST] = None
    line_start: int = 0
    line_end: int = 0
    source: Optional[str] = None
    parent: Optional["UnifiedElement"] = None
    children: List["UnifiedElement"] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        """Make element hashable for use in sets."""
        return hash((self.name, self.type.value, self.line_start))

    def __eq__(self, other):
        """Check equality based on name and type."""
        if not isinstance(other, UnifiedElement):
            return False
        return self.name == other.name and self.type == other.type

    def get_full_name(self) -> str:
        """Get the fully qualified name including parent context."""
        if self.parent:
            return f"{self.parent.get_full_name()}.{self.name}"
        return self.name

    def find_children_by_type(
        self, element_type: ElementType
    ) -> List["UnifiedElement"]:
        """Find all children of a specific type."""
        return [child for child in self.children if child.type == element_type]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "type": self.type.name,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "decorators": self.decorators,
            "metadata": self.metadata,
            "children": [child.to_dict() for child in self.children],
        }


class ElementExtractor:
    """
    Unified element extraction from AST.

    This class provides consistent element extraction across all tools,
    eliminating duplication and ensuring consistency.
    """

    def __init__(self, processor: BaseASTProcessor):
        """
        Initialize extractor with an AST processor.

        Args:
            processor: BaseASTProcessor instance
        """
        self.processor = processor
        self._element_cache: Dict[str, List[UnifiedElement]] = {}

    def extract_all(
        self, include_source: bool = False
    ) -> Dict[ElementType, List[UnifiedElement]]:
        """
        Extract all elements from the AST.

        Args:
            include_source: Whether to include source code in elements

        Returns:
            Dictionary mapping element types to lists of elements
        """
        cache_key = f"all_{include_source}"
        if cache_key in self._element_cache:
            return self._element_cache[cache_key]

        elements = {element_type: [] for element_type in ElementType}

        # Extract module-level elements
        elements[ElementType.MODULE] = [self._create_module_element()]

        # Extract imports
        for node in self.processor.extract_imports():
            element = self._create_import_element(node, include_source)
            if isinstance(node, ast.Import):
                elements[ElementType.IMPORT].append(element)
            else:
                elements[ElementType.IMPORT_FROM].append(element)

        # Extract classes and their contents
        for class_node in self.processor.extract_classes():
            class_element = self._create_class_element(class_node, include_source)
            elements[ElementType.CLASS].append(class_element)

            # Extract class contents
            class_contents = self.processor.extract_class_elements(class_node)

            # Methods
            for method_node in class_contents["methods"]:
                method_element = self._create_method_element(
                    method_node, class_element, include_source
                )
                if isinstance(method_node, ast.AsyncFunctionDef):
                    elements[ElementType.ASYNC_METHOD].append(method_element)
                else:
                    elements[ElementType.METHOD].append(method_element)
                class_element.children.append(method_element)

            # Properties
            for prop_node in class_contents["properties"]:
                prop_element = self._create_property_element(
                    prop_node, class_element, include_source
                )
                elements[ElementType.PROPERTY].append(prop_element)
                class_element.children.append(prop_element)

            # Fields
            for field_node in class_contents["fields"]:
                field_element = self._create_field_element(
                    field_node, class_element, include_source
                )
                elements[ElementType.FIELD].append(field_element)
                class_element.children.append(field_element)

                # Check for special Odoo fields
                if self._is_sql_constraint(field_node):
                    elements[ElementType.SQL_CONSTRAINT].append(field_element)
                    field_element.metadata["is_sql_constraint"] = True
                elif self._is_model_index(field_node):
                    elements[ElementType.MODEL_INDEX].append(field_element)
                    field_element.metadata["is_model_index"] = True

        # Extract top-level functions
        for func_node in self.processor.extract_functions():
            func_element = self._create_function_element(func_node, include_source)
            if isinstance(func_node, ast.AsyncFunctionDef):
                elements[ElementType.ASYNC_FUNCTION].append(func_element)
            else:
                elements[ElementType.FUNCTION].append(func_element)

        # Extract module-level variables
        for assign_node in self.processor.extract_assignments():
            var_element = self._create_variable_element(assign_node, include_source)
            elements[ElementType.MODULE_VAR].append(var_element)

        # Cache results
        self._element_cache[cache_key] = elements

        return elements

    def _create_module_element(self) -> UnifiedElement:
        """Create element for the module itself."""
        docstring = self.processor.get_docstring(self.processor.tree)
        return UnifiedElement(
            name="<module>",
            type=ElementType.MODULE,
            node=self.processor.tree,
            line_start=1,
            line_end=len(self.processor.lines),
            metadata={"docstring": docstring} if docstring else {},
        )

    def _create_import_element(
        self, node: ast.stmt, include_source: bool
    ) -> UnifiedElement:
        """Create element for an import statement."""
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
            name = ", ".join(names)
        else:  # ImportFrom
            module = node.module or ""
            names = [alias.name for alias in node.names]
            name = f"from {module} import {', '.join(names)}"

        start, end = self.processor.get_line_range(node)

        element = UnifiedElement(
            name=name,
            type=(
                ElementType.IMPORT
                if isinstance(node, ast.Import)
                else ElementType.IMPORT_FROM
            ),
            node=node,
            line_start=start,
            line_end=end,
        )

        if include_source:
            element.source = self.processor.get_source_segment(node)

        return element

    def _create_class_element(
        self, node: ast.ClassDef, include_source: bool
    ) -> UnifiedElement:
        """Create element for a class definition."""
        start, end = self.processor.get_line_range(node)
        decorators = [
            self.processor.extract_decorator_name(d) or "" for d in node.decorator_list
        ]

        element = UnifiedElement(
            name=node.name,
            type=ElementType.CLASS,
            node=node,
            line_start=start,
            line_end=end,
            decorators=[d for d in decorators if d],
        )

        # Add metadata
        element.metadata["bases"] = [
            self.processor.unparse_safe(base) for base in node.bases
        ]
        element.metadata["keywords"] = [kw.arg for kw in node.keywords if kw.arg]

        docstring = self.processor.get_docstring(node)
        if docstring:
            element.metadata["docstring"] = docstring

        if include_source:
            element.source = self.processor.get_source_segment(node)

        return element

    def _create_method_element(
        self,
        node: Union[ast.FunctionDef, ast.AsyncFunctionDef],
        parent: UnifiedElement,
        include_source: bool,
    ) -> UnifiedElement:
        """Create element for a method."""
        start, end = self.processor.get_line_range(node)
        decorators = [
            self.processor.extract_decorator_name(d) or "" for d in node.decorator_list
        ]

        element_type = (
            ElementType.ASYNC_METHOD
            if isinstance(node, ast.AsyncFunctionDef)
            else ElementType.METHOD
        )

        element = UnifiedElement(
            name=node.name,
            type=element_type,
            node=node,
            line_start=start,
            line_end=end,
            parent=parent,
            decorators=[d for d in decorators if d],
        )

        # Add metadata
        element.metadata["args"] = [arg.arg for arg in node.args.args]
        element.metadata["returns"] = (
            self.processor.unparse_safe(node.returns) if node.returns else None
        )

        docstring = self.processor.get_docstring(node)
        if docstring:
            element.metadata["docstring"] = docstring

        if include_source:
            element.source = self.processor.get_source_segment(node)

        return element

    def _create_property_element(
        self,
        node: Union[ast.FunctionDef, ast.AsyncFunctionDef],
        parent: UnifiedElement,
        include_source: bool,
    ) -> UnifiedElement:
        """Create element for a property."""
        element = self._create_method_element(node, parent, include_source)
        element.type = ElementType.PROPERTY
        element.metadata["is_property"] = True
        return element

    def _create_field_element(
        self,
        node: Union[ast.Assign, ast.AnnAssign],
        parent: UnifiedElement,
        include_source: bool,
    ) -> UnifiedElement:
        """Create element for a class field."""
        name = self.processor.get_node_name(node)
        if not name:
            name = "<unknown>"

        start, end = self.processor.get_line_range(node)

        element = UnifiedElement(
            name=name,
            type=ElementType.FIELD,
            node=node,
            line_start=start,
            line_end=end,
            parent=parent,
        )

        # Add field value info
        if isinstance(node, ast.Assign):
            element.metadata["value"] = self.processor.unparse_safe(node.value)
        elif isinstance(node, ast.AnnAssign):
            element.metadata["annotation"] = self.processor.unparse_safe(
                node.annotation
            )
            if node.value:
                element.metadata["value"] = self.processor.unparse_safe(node.value)

        if include_source:
            element.source = self.processor.get_source_segment(node)

        return element

    def _create_function_element(
        self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef], include_source: bool
    ) -> UnifiedElement:
        """Create element for a top-level function."""
        start, end = self.processor.get_line_range(node)
        decorators = [
            self.processor.extract_decorator_name(d) or "" for d in node.decorator_list
        ]

        element_type = (
            ElementType.ASYNC_FUNCTION
            if isinstance(node, ast.AsyncFunctionDef)
            else ElementType.FUNCTION
        )

        element = UnifiedElement(
            name=node.name,
            type=element_type,
            node=node,
            line_start=start,
            line_end=end,
            decorators=[d for d in decorators if d],
        )

        # Add metadata
        element.metadata["args"] = [arg.arg for arg in node.args.args]
        element.metadata["returns"] = (
            self.processor.unparse_safe(node.returns) if node.returns else None
        )

        docstring = self.processor.get_docstring(node)
        if docstring:
            element.metadata["docstring"] = docstring

        if include_source:
            element.source = self.processor.get_source_segment(node)

        return element

    def _create_variable_element(
        self, node: ast.Assign, include_source: bool
    ) -> UnifiedElement:
        """Create element for a module-level variable."""
        name = self.processor.get_node_name(node)
        if not name:
            name = "<unknown>"

        start, end = self.processor.get_line_range(node)

        element = UnifiedElement(
            name=name,
            type=ElementType.MODULE_VAR,
            node=node,
            line_start=start,
            line_end=end,
        )

        element.metadata["value"] = self.processor.unparse_safe(node.value)

        if include_source:
            element.source = self.processor.get_source_segment(node)

        return element

    def _is_sql_constraint(self, node: ast.AST) -> bool:
        """Check if a field is an SQL constraint (Odoo specific)."""
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_sql_constraints":
                    return True
        return False

    def _is_model_index(self, node: ast.AST) -> bool:
        """Check if a field is a model index (Odoo specific)."""
        if isinstance(node, ast.Assign):
            # Check if value contains models.Index
            source = self.processor.unparse_safe(node.value)
            if "models.Index" in source or "Index(" in source:
                return True
            for target in node.targets:
                if isinstance(target, ast.Name) and "index" in target.id.lower():
                    return True
        return False

    def find_elements_by_type(self, element_type: ElementType) -> List[UnifiedElement]:
        """Find all elements of a specific type."""
        all_elements = self.extract_all()
        return all_elements.get(element_type, [])
