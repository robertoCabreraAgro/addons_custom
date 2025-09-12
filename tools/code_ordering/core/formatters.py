#!/usr/bin/env python3
"""
Code Formatters and Section Generators

Provides consistent formatting utilities for code reorganization.

Author: Agromarin Tools
Version: 1.0.0
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class SectionHeaderConfig:
    """Configuration for section headers."""

    enabled: bool = True
    separator: str = "="
    separator_length: int = 77
    format: str = "    # {separator}\n    # {title}\n    # {separator}"
    add_empty_line_after: bool = True


class SectionFormatter:
    """Formats section headers and separators."""

    def __init__(self, config: Optional[SectionHeaderConfig] = None):
        """
        Initialize section formatter.

        Args:
            config: Section header configuration
        """
        self.config = config or SectionHeaderConfig()

    def create_header(self, title: str, indent: str = "    ") -> List[str]:
        """
        Create a section header.

        Args:
            title: Section title
            indent: Indentation string

        Returns:
            List of header lines
        """
        if not self.config.enabled:
            return []

        separator = self.config.separator * self.config.separator_length
        header = self.config.format.format(separator=separator, title=title)

        # Add indentation to each line
        lines = [indent + line if line else line for line in header.split("\n")]

        if self.config.add_empty_line_after:
            lines.append("")

        return lines

    def create_simple_header(self, title: str) -> str:
        """
        Create a simple one-line header.

        Args:
            title: Section title

        Returns:
            Single header line
        """
        return f"    # {title}"

    @staticmethod
    def format_docstring(docstring: str, indent: str = "    ") -> List[str]:
        """
        Format a docstring with proper indentation.

        Args:
            docstring: Docstring content
            indent: Indentation string

        Returns:
            List of formatted docstring lines
        """
        if not docstring:
            return []

        lines = [f'{indent}"""']
        for line in docstring.split("\n"):
            if line:
                lines.append(f"{indent}{line}")
            else:
                lines.append("")
        lines.append(f'{indent}"""')
        return lines


class ImportFormatter:
    """Formats import statements."""

    # Standard import group order for Odoo
    IMPORT_GROUP_ORDER = [
        "python_stdlib",
        "third_party",
        "odoo",
        "odoo_addons",
        "relative",
    ]

    @classmethod
    def format_imports(
        cls, import_groups: Dict[str, List[str]], add_spacing: bool = True
    ) -> List[str]:
        """
        Format grouped imports into lines.

        Args:
            import_groups: Dictionary of import groups
            add_spacing: Whether to add spacing between groups

        Returns:
            List of formatted import lines
        """
        lines = []

        for group in cls.IMPORT_GROUP_ORDER:
            group_imports = import_groups.get(group, [])
            if group_imports:
                if lines and add_spacing:
                    lines.append("")
                lines.extend(sorted(group_imports))

        return lines


class FieldFormatter:
    """Formats field declarations."""

    @staticmethod
    def format_field(field_source: str, indent: str = "    ") -> List[str]:
        """
        Format a field declaration with proper indentation.

        Args:
            field_source: Source code of the field
            indent: Indentation string

        Returns:
            List of formatted field lines
        """
        lines = []
        for line in field_source.split("\n"):
            if line.strip():
                lines.append(f"{indent}{line.strip()}")
        return lines

    @staticmethod
    def group_related_fields(
        fields: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group related fields with their base fields.

        Args:
            fields: List of field information dictionaries

        Returns:
            Dictionary mapping base fields to related fields
        """
        grouped = {}
        orphan_fields = []

        for field in fields:
            if field.get("is_related"):
                base_field = field.get("related_base")
                if base_field:
                    if base_field not in grouped:
                        grouped[base_field] = []
                    grouped[base_field].append(field)
                else:
                    orphan_fields.append(field)
            else:
                if field["name"] not in grouped:
                    grouped[field["name"]] = []
                grouped[field["name"]].insert(0, field)  # Base field first

        # Add orphan fields
        for field in orphan_fields:
            grouped[field["name"]] = [field]

        return grouped


class MethodFormatter:
    """Formats method declarations."""

    @staticmethod
    def format_method(
        method_source: str, decorators: List[str], indent: str = "    "
    ) -> List[str]:
        """
        Format a method with its decorators.

        Args:
            method_source: Source code of the method
            decorators: List of decorator strings
            indent: Indentation string

        Returns:
            List of formatted method lines
        """
        lines = []

        # Add decorators first
        for decorator in decorators:
            lines.append(f"{indent}{decorator}")

        # Add method source
        for line in method_source.split("\n"):
            if line.strip():
                lines.append(f"{indent}{line.strip()}")

        return lines

    @staticmethod
    def group_methods_by_category(
        methods: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group methods by their categories.

        Args:
            methods: List of method information dictionaries

        Returns:
            Dictionary mapping categories to methods
        """
        grouped = {}

        for method in methods:
            category = method.get("category", "UNCATEGORIZED")
            if category not in grouped:
                grouped[category] = []
            grouped[category].append(method)

        return grouped


class CodeBlockFormatter:
    """Formats complete code blocks."""

    def __init__(
        self,
        section_formatter: Optional[SectionFormatter] = None,
        import_formatter: Optional[ImportFormatter] = None,
        field_formatter: Optional[FieldFormatter] = None,
        method_formatter: Optional[MethodFormatter] = None,
    ):
        """Initialize code block formatter with component formatters."""
        self.section = section_formatter or SectionFormatter()
        self.imports = import_formatter or ImportFormatter()
        self.fields = field_formatter or FieldFormatter()
        self.methods = method_formatter or MethodFormatter()

    def format_class_body(
        self,
        class_info: Dict[str, Any],
        field_strategy: str = "semantic",
        add_headers: bool = True,
    ) -> List[str]:
        """
        Format a complete class body.

        Args:
            class_info: Dictionary containing class information
            field_strategy: Field ordering strategy
            add_headers: Whether to add section headers

        Returns:
            List of formatted class body lines
        """
        lines = []

        # Add docstring
        if class_info.get("docstring"):
            lines.extend(self.section.format_docstring(class_info["docstring"]))
            lines.append("")

        # Add model attributes
        if class_info.get("model_attributes"):
            for attr in class_info["model_attributes"]:
                lines.append(f"    {attr}")
            lines.append("")

        # Add fields
        if class_info.get("fields"):
            if add_headers:
                lines.extend(self.section.create_header("FIELDS"))

            # Format fields based on strategy
            if field_strategy == "semantic":
                field_groups = class_info.get("field_groups", {})
                for group_name, fields in field_groups.items():
                    if add_headers and len(field_groups) > 1:
                        lines.append(
                            self.section.create_simple_header(f"{group_name} Fields")
                        )
                    for field in fields:
                        lines.extend(self.fields.format_field(field["source"]))
                    lines.append("")
            else:
                for field in class_info["fields"]:
                    lines.extend(self.fields.format_field(field["source"]))
                lines.append("")

        # Add methods
        if class_info.get("methods"):
            method_groups = self.methods.group_methods_by_category(
                class_info["methods"]
            )
            for category, methods in method_groups.items():
                if add_headers:
                    lines.extend(self.section.create_header(f"{category} METHODS"))
                for method in methods:
                    lines.extend(
                        self.methods.format_method(
                            method["source"], method.get("decorators", [])
                        )
                    )
                    lines.append("")

        return lines
