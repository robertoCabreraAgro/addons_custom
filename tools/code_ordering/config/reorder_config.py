"""
Configuration for code reordering operations.

This module provides configuration specific to the reordering tool.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .base import BaseConfig


@dataclass
class ReorderConfig(BaseConfig):
    """
    Configuration for code reordering operations.

    Controls how code is reorganized and formatted.
    """

    # File processing
    encoding: str = "utf-8"
    backup_suffix: str = ".bak"
    create_backup: bool = True
    dry_run: bool = False

    # Black formatting
    use_black: bool = True
    line_length: int = 88
    target_python_version: str = "3.8"
    string_normalization: bool = True
    magic_trailing_comma: bool = True

    # Section headers
    add_section_headers: bool = True
    section_separator: str = "-" * 60
    section_header_format: str = "    # {separator}\n    # {title}\n    # {separator}"

    # Section order and titles
    section_order: List[str] = field(
        default_factory=lambda: [
            "model_attributes",
            "fields",
            "indexes",
            "sql_constraints",
            "constraints",
            "crud",
            "compute",
            "inverse",
            "search",
            "onchange",
            "actions",
            "helpers",
            "private",
            "public",
            "override",
        ]
    )

    section_titles: Dict[str, str] = field(
        default_factory=lambda: {
            "model_attributes": "MODEL ATTRIBUTES",
            "fields": "FIELDS",
            "indexes": "INDEXES",
            "sql_constraints": "SQL CONSTRAINTS",
            "constraints": "CONSTRAINT METHODS",
            "crud": "CRUD METHODS",
            "compute": "COMPUTE METHODS",
            "inverse": "INVERSE METHODS",
            "search": "SEARCH METHODS",
            "onchange": "ONCHANGE METHODS",
            "actions": "ACTION METHODS",
            "helpers": "HELPERS",
            "private": "PRIVATE METHODS",
            "public": "PUBLIC METHODS",
            "override": "OVERRIDE METHODS",
        }
    )

    # Method organization
    group_methods_by_type: bool = True
    sort_methods_alphabetically: bool = False
    preserve_method_order_in_group: bool = True

    # Field organization
    group_fields_by_type: bool = True
    field_type_order: List[str] = field(
        default_factory=lambda: [
            "relational",  # Many2one, One2many, Many2many
            "basic",  # Char, Text, Integer, Float, etc.
            "date",  # Date, Datetime
            "selection",  # Selection
            "binary",  # Binary, Image
            "computed",  # Fields with compute parameter
            "special",  # Other fields
        ]
    )

    # Import organization
    organize_imports: bool = True
    import_group_order: List[str] = field(
        default_factory=lambda: [
            "python_stdlib",
            "third_party",
            "odoo",
            "odoo_addons",
            "relative",
        ]
    )
    sort_imports_alphabetically: bool = True

    # Cache settings
    use_cache: bool = True
    cache_ttl: int = 3600  # 1 hour
    max_cache_size: int = 1000

    # Output settings
    output_dir: Optional[str] = None
    preserve_file_structure: bool = True
    verbose: bool = False

    # Processing limits
    max_file_size_mb: int = 10
    max_files_per_batch: int = 50

    @classmethod
    def get_default(cls) -> "ReorderConfig":
        """Get default reorder configuration."""
        return cls()

    def get_section_header(self, section: str) -> str:
        """Generate section header for a given section."""
        if not self.add_section_headers:
            return ""

        title = self.section_titles.get(section, section.upper())
        return self.section_header_format.format(
            separator=self.section_separator, title=title
        )

    def should_process_file(self, file_size_bytes: int) -> bool:
        """Check if a file should be processed based on size."""
        max_bytes = self.max_file_size_mb * 1024 * 1024
        return file_size_bytes <= max_bytes
