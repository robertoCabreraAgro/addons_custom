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


def format_section_header(
    title: str,
    separator: str = "=",
    length: int = 77,
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
