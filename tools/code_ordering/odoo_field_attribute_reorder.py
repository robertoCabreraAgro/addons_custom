#!/usr/bin/env python3
"""
Odoo Field Attribute Reordering Tool

This tool reorders field attributes in Odoo Python files according to
Odoo conventions, without changing field order or any other code structure.
Only the attributes within field definitions are reordered.
"""

import argparse
import ast
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
import shutil


# Import the ordering patterns from core
try:
    from core.ordering import Ordering
except ImportError:
    import sys

    sys.path.append(str(Path(__file__).parent))
    from core.ordering import Ordering


@dataclass
class FieldAttributeInfo:
    """Information about a field definition and its attributes."""

    file_path: str
    line_number: int
    field_name: str
    field_type: str
    original_code: str
    reordered_code: str
    attributes: dict[str, str]


class FieldAttributeReorderer:
    """Reorders field attributes according to Odoo conventions."""

    def __init__(self, dry_run: bool = False, backup: bool = False):
        self.dry_run = dry_run
        self.backup = backup
        self.ordering = Ordering()
        self.modifications = []

        # Build FIELD_ATTRIBUTE_ORDER from the Ordering class
        # This is a dictionary mapping field types to their attribute order
        self.field_attribute_order = self._build_field_attribute_order()

        # Define positional argument mappings for each field type
        self.positional_arg_map = self._build_positional_arg_map()

    def _build_positional_arg_map(self) -> dict[str, list[str]]:
        """Build mapping of positional arguments for each field type.

        Returns a dictionary where:
        - Key: field type name
        - Value: list of parameter names in order for positional arguments
        """
        return {
            # Relational fields
            "Many2one": ["comodel_name", "string"],
            "One2many": ["comodel_name", "inverse_name", "string"],
            "Many2many": ["comodel_name", "relation", "column1", "column2", "string"],
            # Basic fields - most have 'string' as first positional
            "Char": ["string"],
            "Text": ["string"],
            "Html": ["string"],
            "Integer": ["string"],
            "Float": ["string"],
            "Monetary": ["string"],
            "Boolean": ["string"],
            "Date": ["string"],
            "Datetime": ["string"],
            "Binary": ["string"],
            "Image": ["string"],
            # Selection has selection list first, then string
            "Selection": ["selection", "string"],
            # Reference has selection list, then string
            "Reference": ["selection", "string"],
            # Json and Properties
            "Json": ["string"],
            "Properties": ["string"],
        }

    def _build_field_attribute_order(self) -> dict[str, list[str]]:
        """Build field attribute order dictionary from Ordering class."""
        # The Ordering class in core/ordering.py has the attribute orders
        # defined directly in the class. Let's use them.
        return {
            # Relational fields
            "Many2one": [
                "related",
                "comodel_name",
                "string",
                "required",
                "default",
                "change_default",
                "compute",
                "compute_sudo",
                "store",
                "precompute",
                "recursive",
                "readonly",
                "inverse",
                "search",
                "bypass_search_access",
                "company_dependent",
                "check_company",
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
                "depends",
                "comodel_name",
                "relation",
                "column1",
                "column2",
                "string",
                "required",
                "compute",
                "compute_sudo",
                "store",
                "precompute",
                "recursive",
                "readonly",
                "inverse",
                "search",
                "check_company",
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
                "default",
                "size",
                "trim",
                "translate",
                "compute",
                "store",
                "precompute",
                "recursive",
                "readonly",
                "inverse",
                "search",
                "copy",
                "groups",
                "index",
                "tracking",
                "config_parameter",
                "help",
            ],
            "Text": [
                "related",
                "string",
                "required",
                "default",
                "translate",
                "compute",
                "store",
                "precompute",
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
                "default",
                "translate",
                "sanitize",
                "sanitize_tags",
                "sanitize_attributes",
                "sanitize_style",
                "strip_style",
                "strip_classes",
                "compute",
                "store",
                "precompute",
                "readonly",
                "inverse",
                "search",
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
                "default",
                "compute",
                "compute_sudo",
                "store",
                "precompute",
                "readonly",
                "inverse",
                "search",
                "company_dependent",
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
                "default",
                "compute",
                "compute_sudo",
                "store",
                "precompute",
                "readonly",
                "inverse",
                "search",
                "company_dependent",
                "aggregator",
                "group_operator",
                "copy",
                "groups",
                "index",
                "tracking",
                "help",
            ],
            "Monetary": [
                "related",
                "string",
                "currency_field",
                "required",
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
            # Date/time fields
            "Date": [
                "related",
                "string",
                "required",
                "default",
                "compute",
                "store",
                "precompute",
                "readonly",
                "inverse",
                "search",
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
                "default",
                "compute",
                "store",
                "precompute",
                "readonly",
                "inverse",
                "search",
                "copy",
                "groups",
                "index",
                "tracking",
                "help",
            ],
            # Selection field
            "Selection": [
                "related",
                "depends",
                "selection",
                "selection_add",
                "string",
                "required",
                "default",
                "compute",
                "store",
                "precompute",
                "readonly",
                "inverse",
                "search",
                "ondelete",
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
                "default",
                "compute",
                "compute_sudo",
                "store",
                "precompute",
                "readonly",
                "inverse",
                "search",
                "company_dependent",
                "copy",
                "implied_group",
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
                "default",
                "readonly",
                "attachment",
                "compute",
                "store",
                "inverse",
                "search",
                "copy",
                "exportable",
                "groups",
                "help",
            ],
            "Image": [
                "related",
                "string",
                "required",
                "default",
                "attachment",
                "max_width",
                "max_height",
                "verify_resolution",
                "compute",
                "store",
                "readonly",
                "inverse",
                "search",
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
                "default",
                "compute",
                "store",
                "readonly",
                "inverse",
                "search",
                "copy",
                "groups",
                "help",
            ],
            "Json": [
                "related",
                "string",
                "required",
                "default",
                "compute",
                "store",
                "readonly",
                "inverse",
                "search",
                "copy",
                "groups",
                "help",
            ],
            "Properties": [
                "related",
                "string",
                "definition",
                "required",
                "compute",
                "store",
                "readonly",
                "inverse",
                "search",
                "copy",
                "groups",
                "help",
            ],
        }

    def process_file(self, file_path: Path) -> list[FieldAttributeInfo]:
        """Process a single Python file and reorder field attributes."""
        if not file_path.exists() or not file_path.suffix == ".py":
            print(f"Skipping {file_path}: Not a Python file")
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                original_content = content
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return []

        # Parse the file to find field definitions
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            print(f"Syntax error in {file_path}: {e}")
            return []

        # Find all field definitions and their locations
        field_definitions = self._find_field_definitions(tree, str(file_path))

        # Process each field definition
        modifications = []
        lines = content.splitlines()

        for field_def in field_definitions:
            # Extract the field definition from source
            start_line = field_def["line"] - 1  # AST uses 1-based indexing
            field_code = self._extract_field_definition(lines, start_line)

            if not field_code:
                continue

            # Reorder the field attributes
            reordered_code = self._reorder_field_attributes(
                field_code, field_def["type"]
            )

            # Only record if there's a change
            if field_code != reordered_code:
                modification = FieldAttributeInfo(
                    file_path=str(file_path),
                    line_number=field_def["line"],
                    field_name=field_def["name"],
                    field_type=field_def["type"],
                    original_code=field_code,
                    reordered_code=reordered_code,
                    attributes=field_def.get("attributes", {}),
                )
                modifications.append(modification)

        # Apply modifications if not dry run
        if modifications and not self.dry_run:
            self._apply_modifications(file_path, original_content, modifications)

        return modifications

    def _find_field_definitions(self, tree: ast.Module, file_path: str) -> list[dict]:
        """Find all field definitions in an AST tree."""
        field_definitions = []

        class FieldVisitor(ast.NodeVisitor):
            def __init__(self, parent_reorderer):
                self.current_class = None
                self.fields = []
                self.parent_reorderer = parent_reorderer
                self.ordering = parent_reorderer.ordering
                self.field_attribute_order = parent_reorderer.field_attribute_order

            def visit_ClassDef(self, node):
                old_class = self.current_class
                self.current_class = node.name
                self.generic_visit(node)
                self.current_class = old_class

            def visit_Assign(self, node):
                if not self.current_class:
                    return

                # Check if this is a field assignment
                if isinstance(node.value, ast.Call):
                    if isinstance(node.value.func, ast.Attribute):
                        if hasattr(node.value.func, "attr"):
                            field_type = node.value.func.attr
                            # Check if it's a field type
                            if (
                                field_type in self.field_attribute_order
                                or field_type
                                in {
                                    "Char",
                                    "Text",
                                    "Integer",
                                    "Float",
                                    "Boolean",
                                    "Date",
                                    "Datetime",
                                    "Binary",
                                    "Selection",
                                    "Many2one",
                                    "One2many",
                                    "Many2many",
                                    "Reference",
                                    "Image",
                                    "Json",
                                    "Properties",
                                    "Html",
                                    "Monetary",
                                }
                            ):

                                # Get field name
                                if node.targets and isinstance(
                                    node.targets[0], ast.Name
                                ):
                                    field_name = node.targets[0].id

                                    # Extract attributes
                                    attributes = self._extract_attributes(node.value)

                                    self.fields.append(
                                        {
                                            "name": field_name,
                                            "type": field_type,
                                            "line": node.lineno,
                                            "class": self.current_class,
                                            "attributes": attributes,
                                        }
                                    )

            def _extract_attributes(self, call_node):
                """Extract attributes from a field call node."""
                attrs = {}

                # Extract keyword arguments
                for keyword in call_node.keywords:
                    if keyword.arg:
                        attrs[keyword.arg] = (
                            ast.unparse(keyword.value)
                            if hasattr(ast, "unparse")
                            else str(keyword.value)
                        )

                # Extract positional arguments (less common for fields)
                if call_node.args:
                    # First positional arg is usually 'string' for most fields
                    # or comodel_name for relational fields
                    if len(call_node.args) > 0:
                        attrs["_positional_0"] = (
                            ast.unparse(call_node.args[0])
                            if hasattr(ast, "unparse")
                            else str(call_node.args[0])
                        )

                return attrs

        visitor = FieldVisitor(self)
        visitor.visit(tree)
        return visitor.fields

    def _extract_field_definition(
        self, lines: list[str], start_line: int
    ) -> str | None:
        """Extract complete field definition from source lines."""
        if start_line >= len(lines):
            return None

        # Start with the line containing the field assignment
        field_lines = []
        current_line = start_line

        # Find the complete field definition (might span multiple lines)
        open_parens = 0
        in_field = False

        while current_line < len(lines):
            line = lines[current_line]

            # Check if this line starts a field definition
            if current_line == start_line:
                if "fields." in line:
                    in_field = True
                else:
                    return None

            if in_field:
                field_lines.append(line)

                # Count parentheses to find the end
                open_parens += line.count("(") - line.count(")")

                # If we've closed all parentheses, we're done
                if open_parens <= 0 and "(" in "".join(field_lines):
                    break

            current_line += 1

        return "\n".join(field_lines) if field_lines else None

    def _reorder_field_attributes(self, field_code: str, field_type: str) -> str:
        """Reorder attributes in a field definition according to conventions."""

        # Parse the field definition to extract components
        match = re.match(
            r"^(\s*)(\w+)\s*=\s*fields\.(\w+)\((.*)\)(.*)$", field_code, re.DOTALL
        )

        if not match:
            return field_code  # Can't parse, return as is

        indent = match.group(1)
        field_name = match.group(2)
        field_class = match.group(3)
        attributes_str = match.group(4)
        trailing = match.group(5)

        if not attributes_str.strip():
            return field_code  # No attributes to reorder

        # Parse attributes
        attributes = self._parse_attributes(attributes_str, field_class)

        if not attributes:
            return field_code  # No attributes found

        # Get the correct attribute order for this field type
        if field_type in self.field_attribute_order:
            attr_order = self.field_attribute_order[field_type]
        else:
            attr_order = self.ordering.FIELD_ATTRIBUTE_GENERIC

        # Reorder attributes
        reordered_attrs = self._order_attributes(attributes, attr_order)

        # Reconstruct the field definition
        if self._should_use_multiline(reordered_attrs):
            return self._format_multiline_field(
                indent, field_name, field_class, reordered_attrs, trailing
            )
        else:
            return self._format_single_line_field(
                indent, field_name, field_class, reordered_attrs, trailing
            )

    def _parse_attributes(
        self, attributes_str: str, field_type: str
    ) -> list[tuple[str, str, bool]]:
        """Parse field attributes from a string.
        Returns list of (name, value, is_positional) tuples."""
        attributes = []
        comments = []  # Store inline comments

        # First, extract and preserve comments
        lines = attributes_str.split("\n")
        processed_lines = []
        for line in lines:
            # Check for comments (but not inside strings)
            in_string = False
            quote_char = None
            comment_idx = -1

            for i, char in enumerate(line):
                if char in ('"', "'") and (i == 0 or line[i - 1] != "\\"):
                    if not in_string:
                        in_string = True
                        quote_char = char
                    elif char == quote_char:
                        in_string = False
                        quote_char = None
                elif char == "#" and not in_string:
                    comment_idx = i
                    break

            if comment_idx >= 0:
                # Store the comment
                comments.append(line[comment_idx:].strip())
                # Keep only the code part
                processed_lines.append(line[:comment_idx].rstrip())
            else:
                processed_lines.append(line)

        # Join processed lines back
        attributes_str = "\n".join(processed_lines)

        # Split by commas not inside parentheses or quotes
        parts = []
        current = []
        depth = 0
        in_string = False
        quote_char = None

        for i, char in enumerate(attributes_str):
            if char in ('"', "'") and (i == 0 or attributes_str[i - 1] != "\\"):
                if not in_string:
                    in_string = True
                    quote_char = char
                elif char == quote_char:
                    in_string = False
                    quote_char = None

            if not in_string:
                if char in "([{":
                    depth += 1
                elif char in ")]}":
                    depth -= 1
                elif char == "," and depth == 0:
                    parts.append("".join(current).strip())
                    current = []
                    continue

            current.append(char)

        if current:
            parts.append("".join(current).strip())

        # Get positional argument mapping for this field type
        positional_param_names = self.positional_arg_map.get(field_type, ["string"])

        # Parse each part
        positional_count = 0
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if "=" in part and not part.startswith("lambda"):
                # Named argument
                key, value = part.split("=", 1)
                attributes.append((key.strip(), value.strip(), False))
            else:
                # Positional argument - convert to named
                if positional_count < len(positional_param_names):
                    # Convert to named argument using the mapping
                    param_name = positional_param_names[positional_count]
                    attributes.append((param_name, part.strip(), False))
                else:
                    # Unknown positional argument, keep as is
                    attributes.append((f"_pos_{positional_count}", part.strip(), True))
                positional_count += 1

        # Store comments as a special attribute to preserve them
        if comments:
            attributes.append(("_comments", comments, False))

        return attributes

    def _order_attributes(
        self, attributes: list[tuple[str, str, bool]], order: list[str]
    ) -> list[tuple[str, str, bool]]:
        """Order attributes according to the specified order."""

        # Extract comments separately (they should be preserved but not reordered)
        comments = None
        regular_attrs = []

        for attr in attributes:
            if attr[0] == "_comments":
                comments = attr
            else:
                regular_attrs.append(attr)

        # Separate positional and named arguments
        positional = [attr for attr in regular_attrs if attr[2]]
        named = {attr[0]: attr for attr in regular_attrs if not attr[2]}

        # Build ordered list
        ordered = []

        # Add positional arguments first
        ordered.extend(positional)

        # Add named arguments in order
        for attr_name in order:
            if attr_name in named:
                ordered.append(named[attr_name])
                del named[attr_name]

        # Add any remaining named arguments not in the order list
        for attr in named.values():
            ordered.append(attr)

        # Add comments at the end (they'll be placed appropriately during formatting)
        if comments:
            ordered.append(comments)

        return ordered

    def _should_use_multiline(self, attributes: list[tuple[str, str, bool]]) -> bool:
        """Determine if field should be formatted as multiline."""
        # Use multiline if:
        # - Has comments
        # - More than 3 attributes
        # - Any attribute value is long
        # - Total length would exceed 88 characters

        # Check for comments
        for name, value, _ in attributes:
            if name == "_comments":
                return True  # Always use multiline if there are comments

        if len(attributes) > 3:
            return True

        for name, value, _ in attributes:
            if len(value) > 40:
                return True
            if "\n" in value:
                return True

        # Estimate single line length
        total_length = sum(len(name) + len(value) + 3 for name, value, _ in attributes)
        return total_length > 60

    def _format_multiline_field(
        self,
        indent: str,
        field_name: str,
        field_class: str,
        attributes: list[tuple[str, str, bool]],
        trailing: str,
    ) -> str:
        """Format field definition as multiline."""
        lines = [f"{indent}{field_name} = fields.{field_class}("]

        # Separate comments from regular attributes
        comments = None
        regular_attrs = []
        for name, value, is_pos in attributes:
            if name == "_comments":
                comments = value
            else:
                regular_attrs.append((name, value, is_pos))

        for i, (name, value, is_positional) in enumerate(regular_attrs):
            if is_positional:
                # Positional argument
                if name.startswith("_pos_"):
                    lines.append(f"{indent}    {value},")
            else:
                # Named argument
                lines.append(f"{indent}    {name}={value},")

        # Add comments back if they exist
        if comments:
            # Insert comments before the last added line if appropriate
            for comment in comments:
                # Find the right place to insert the comment based on context
                # For now, add them after the attribute they follow
                lines.insert(-1, f"{indent}    {comment}")

        lines.append(f"{indent}){trailing}")

        return "\n".join(lines)

    def _format_single_line_field(
        self,
        indent: str,
        field_name: str,
        field_class: str,
        attributes: list[tuple[str, str, bool]],
        trailing: str,
    ) -> str:
        """Format field definition as single line."""
        attr_parts = []

        # Filter out comments for single-line format
        # (comments should trigger multiline format anyway)
        for name, value, is_positional in attributes:
            if name == "_comments":
                continue  # Skip comments in single-line format
            if is_positional:
                attr_parts.append(value)
            else:
                attr_parts.append(f"{name}={value}")

        attrs_str = ", ".join(attr_parts)
        return f"{indent}{field_name} = fields.{field_class}({attrs_str}){trailing}"

    def _apply_modifications(
        self,
        file_path: Path,
        original_content: str,
        modifications: list[FieldAttributeInfo],
    ):
        """Apply modifications to the file."""

        # Create backup if requested
        if self.backup:
            backup_path = file_path.with_suffix(
                f'.bak.{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            )
            shutil.copy2(file_path, backup_path)
            print(f"Backup created: {backup_path}")

        # Apply modifications
        lines = original_content.splitlines(keepends=True)

        # Sort modifications by line number in reverse to avoid offset issues
        for mod in sorted(modifications, key=lambda x: x.line_number, reverse=True):
            # Find and replace the field definition
            start_line = mod.line_number - 1

            # Find the extent of the original field definition
            old_lines = mod.original_code.splitlines()

            # Replace with new definition
            new_lines = mod.reordered_code.splitlines(keepends=True)

            # Ensure newlines are preserved
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines[-1] += "\n"

            # Replace the lines
            for i in range(len(old_lines)):
                if start_line + i < len(lines):
                    if i < len(new_lines):
                        lines[start_line + i] = new_lines[i]
                    else:
                        lines[start_line + i] = ""

            # Add any extra lines if new definition is longer
            if len(new_lines) > len(old_lines):
                for i in range(len(old_lines), len(new_lines)):
                    lines.insert(start_line + i, new_lines[i])

        # Write the modified content
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        print(f"✓ Modified {file_path}: {len(modifications)} fields reordered")

    def process_directory(
        self, directory: Path, recursive: bool = False
    ) -> list[FieldAttributeInfo]:
        """Process all Python files in a directory."""
        all_modifications = []

        pattern = "**/*.py" if recursive else "*.py"

        for py_file in directory.glob(pattern):
            if "__pycache__" in str(py_file):
                continue

            modifications = self.process_file(py_file)
            all_modifications.extend(modifications)

        return all_modifications

    def generate_report(self, modifications: list[FieldAttributeInfo]) -> str:
        """Generate a summary report of modifications."""
        if not modifications:
            return "No field attributes needed reordering."

        report_lines = [
            "Field Attribute Reordering Report",
            "=" * 40,
            f"Total fields processed: {len(modifications)}",
            "",
            "Modified fields:",
            "-" * 20,
        ]

        # Group by file
        by_file = {}
        for mod in modifications:
            if mod.file_path not in by_file:
                by_file[mod.file_path] = []
            by_file[mod.file_path].append(mod)

        for file_path, file_mods in sorted(by_file.items()):
            report_lines.append(f"\n{file_path}:")
            for mod in file_mods:
                report_lines.append(
                    f"  Line {mod.line_number}: {mod.field_name} ({mod.field_type})"
                )
                report_lines.append(f"    Before: {mod.original_code[:50]}...")
                report_lines.append(f"    After:  {mod.reordered_code[:50]}...")

        return "\n".join(report_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Reorder Odoo field attributes according to conventions"
    )

    parser.add_argument("path", type=str, help="File or directory to process")

    parser.add_argument(
        "--recursive", "-r", action="store_true", help="Process directories recursively"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview changes without modifying files",
    )

    parser.add_argument(
        "--backup",
        action="store_true",
        default=False,
        help="Create backup files before modifying",
    )

    parser.add_argument(
        "--report", action="store_true", help="Generate detailed report"
    )

    args = parser.parse_args()

    # Create reorderer
    reorderer = FieldAttributeReorderer(dry_run=args.dry_run, backup=args.backup)

    # Process path
    path = Path(args.path)

    if path.is_file():
        modifications = reorderer.process_file(path)
    elif path.is_dir():
        modifications = reorderer.process_directory(path, recursive=args.recursive)
    else:
        print(f"Error: {path} not found")
        return 1

    # Show results
    if modifications:
        print(f"\nFound {len(modifications)} fields that need attribute reordering")

        if args.report or args.dry_run:
            print("\n" + reorderer.generate_report(modifications))

        if args.dry_run:
            print(
                "\n[DRY RUN] No files were modified. Remove --dry-run to apply changes."
            )
    else:
        print("All field attributes are already properly ordered!")

    return 0


if __name__ == "__main__":
    exit(main())
