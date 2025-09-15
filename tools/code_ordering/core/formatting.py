#!/usr/bin/env python3
"""
Formatting functions for code reorganization.

This module provides utility functions for formatting various code elements
during the reorganization process. All functions are stateless and designed
for easy composition.

The formatting functions handle:
- Section headers for code organization
- Docstring formatting with proper indentation
- Import statement formatting and grouping
- Field and method formatting
- Complete class body reconstruction
"""

from typing import Any, Optional


def format_section_header(
    title: str, separator: str = "=", length: int = 77
) -> list[str]:
    """Format a prominent section header with separator lines.

    Creates a three-line header comment block for visually separating
    major sections in the code (e.g., FIELDS, CRUD METHODS).

    Args:
        title: Section title to display
        separator: Character to use for separator lines (default '=')
        length: Total length of separator lines (default 77)

    Returns:
        list[str]: Four lines - separator, title, separator, blank line

    Example:
        >>> format_section_header("FIELDS")
        ['    # =====================================================',
         '    # FIELDS',
         '    # =====================================================',
         '']
    """
    sep_line = separator * length
    return [
        f"    # {sep_line}",
        f"    # {title}",
        f"    # {sep_line}",
        "",
    ]


def format_simple_header(title: str) -> str:
    """Format a simple one-line comment header.

    Creates a single-line comment for minor section headers.

    Args:
        title: Section title to display

    Returns:
        str: Single comment line with title

    Example:
        >>> format_simple_header("Helper Methods")
        '    # Helper Methods'
    """
    return f"    # {title}"


def format_docstring(docstring: str, indent: str = "    ") -> list[str]:
    """Format a docstring with proper indentation and triple quotes.

    Ensures docstrings are properly formatted with correct indentation
    and Python triple-quote syntax.

    Args:
        docstring: Raw docstring content (without triple quotes)
        indent: Indentation string to prepend (default 4 spaces)

    Returns:
        list[str]: Formatted docstring lines including triple quotes,
                  or empty list if docstring is empty
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


def format_imports(
    imports: list[str], group_order: Optional[list[str]] = None
) -> list[str]:
    """Format and sort import statements using isort.

    Uses isort to properly group and sort imports according to
    Odoo conventions (stdlib, third-party, odoo, odoo.addons, relative).

    Args:
        imports: List of import statement strings
        group_order: Optional list defining group order (currently unused,
                    isort configuration is used instead)

    Returns:
        list[str]: Sorted and grouped import statements
    """
    if not imports:
        return []

    try:
        import isort

        # Join imports into a single string
        import_str = "\n".join(imports)

        # Use isort with Odoo configuration
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
    except ImportError:
        # Fallback to simple alphabetical sorting if isort not available
        return sorted(imports)


def format_field(field_source: str, indent: str = "    ") -> list[str]:
    """Format a field declaration with proper indentation.

    Handles multi-line field definitions, ensuring consistent indentation.

    Args:
        field_source: Source code of the field definition
        indent: Indentation string to prepend (default 4 spaces)

    Returns:
        list[str]: Field lines with proper indentation
    """
    lines = []
    for line in field_source.split("\n"):
        if line.strip():
            lines.append(f"{indent}{line.strip()}")
    return lines


def format_method(
    method_source: str, decorators: list[str], indent: str = "    "
) -> list[str]:
    """Format a method with its decorators.

    Combines decorators and method source with proper indentation,
    ensuring decorators appear before the method definition.

    Args:
        method_source: Source code of the method definition
        decorators: List of decorator strings (with @ prefix)
        indent: Indentation string to prepend (default 4 spaces)

    Returns:
        list[str]: Complete method with decorators, properly indented
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


def format_class_body(
    class_info: dict[str, Any],
    add_headers: bool = True,
    field_strategy: str = "semantic",
) -> list[str]:
    """Format a complete class body with all its elements.

    Reconstructs a class body from parsed information, organizing
    elements in the standard order: docstring, model attributes,
    fields, and methods (grouped by category).

    Args:
        class_info: Dictionary containing:
                   - 'docstring': Class docstring
                   - 'model_attributes': List of model attribute assignments
                   - 'fields': List of field dictionaries with 'source' key
                   - 'methods': List of method dictionaries with 'source',
                               'decorators', and 'category' keys
        add_headers: Whether to add section header comments (default True)
        field_strategy: Field ordering strategy ('semantic' or 'type')

    Returns:
        list[str]: Complete formatted class body lines
    """
    lines = []

    # Add docstring
    if class_info.get("docstring"):
        lines.extend(format_docstring(class_info["docstring"]))
        lines.append("")

    # Add model attributes
    if class_info.get("model_attributes"):
        for attr in class_info["model_attributes"]:
            lines.append(f"    {attr}")
        lines.append("")

    # Add fields
    if class_info.get("fields"):
        if add_headers:
            lines.extend(format_section_header("FIELDS"))

        for field in class_info["fields"]:
            lines.extend(format_field(field.get("source", "")))
        lines.append("")

    # Add methods by category
    if class_info.get("methods"):
        method_categories = {}
        for method in class_info["methods"]:
            category = method.get("category", "UNCATEGORIZED")
            if category not in method_categories:
                method_categories[category] = []
            method_categories[category].append(method)

        for category, methods in method_categories.items():
            if add_headers:
                lines.extend(format_section_header(f"{category} METHODS"))
            for method in methods:
                lines.extend(
                    format_method(
                        method.get("source", ""), method.get("decorators", [])
                    )
                )
                lines.append("")

    return lines


def indent_lines(lines: list[str], indent: str = "    ") -> list[str]:
    """Add indentation to a list of lines.

    Preserves empty lines (doesn't indent them).

    Args:
        lines: Lines to indent
        indent: Indentation string to prepend (default 4 spaces)

    Returns:
        list[str]: Lines with added indentation, empty lines unchanged
    """
    return [f"{indent}{line}" if line else line for line in lines]


def join_lines(lines: list[str]) -> str:
    """Join lines into a single string with newline separators.

    Utility function for combining formatted lines into final output.

    Args:
        lines: List of line strings

    Returns:
        str: Single string with lines joined by newline characters
    """
    return "\n".join(lines)
