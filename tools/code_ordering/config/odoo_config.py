"""
Odoo-specific configuration.

This module provides configuration for Odoo-specific features and versions.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set

from .base import BaseConfig


class OdooVersion(Enum):
    """Supported Odoo versions."""

    V17_0 = "17.0"
    V18_0 = "18.0"
    V19_0 = "19.0"

    @classmethod
    def from_string(cls, version: str) -> "OdooVersion":
        """Create from version string."""
        for v in cls:
            if v.value == version:
                return v
        raise ValueError(f"Unsupported Odoo version: {version}")


@dataclass
class OdooConfig(BaseConfig):
    """
    Configuration for Odoo-specific features.

    Consolidates all Odoo-related configuration in one place.
    """

    # Version settings
    version: str = "19.0"

    # Module detection patterns
    manifest_files: List[str] = field(
        default_factory=lambda: ["__manifest__.py", "__openerp__.py"]
    )

    # Special directories
    special_dirs: List[str] = field(
        default_factory=lambda: [
            "models",
            "views",
            "controllers",
            "wizards",
            "reports",
            "data",
            "security",
            "static",
            "tests",
        ]
    )

    # Skip directories
    skip_dirs: List[str] = field(
        default_factory=lambda: [
            "__pycache__",
            ".git",
            ".svn",
            ".hg",
            "node_modules",
            "venv",
            "env",
            ".venv",
            ".env",
        ]
    )

    # Field types (consolidated from multiple versions)
    field_types: Set[str] = field(
        default_factory=lambda: {
            # Basic fields
            "Boolean",
            "Integer",
            "Float",
            "Monetary",
            "Char",
            "Text",
            "Date",
            "Datetime",
            "Binary",
            "Image",
            "Selection",
            "Html",
            "Json",
            # Relational fields
            "Many2one",
            "One2many",
            "Many2many",
            # Special fields
            "Reference",
            "Many2oneReference",
            "Properties",
            # Computed fields
            "Command",
        }
    )

    # Decorator patterns
    api_decorators: Set[str] = field(
        default_factory=lambda: {
            "api.model",
            "api.depends",
            "api.depends_context",
            "api.onchange",
            "api.constrains",
            "api.returns",
            "api.autovacuum",
            "api.model_create_multi",
            "api.ondelete",
            "api.readonly",
            "tools.ormcache",
            "@model",
            "@depends",
            "@depends_context",
            "@onchange",
            "@constrains",
            "@returns",
            "@autovacuum",
            "@model_create_multi",
            "@ondelete",
            "@readonly",
            "@ormcache",
        }
    )

    # Method type patterns
    method_patterns: Dict[str, List[str]] = field(
        default_factory=lambda: {
            "compute": ["_compute_", "_get_"],
            "inverse": ["_set_", "_inverse_"],
            "search": ["_search_"],
            "constraint": ["_check_", "_validate_"],
            "onchange": ["_onchange_", "onchange_"],
            "action": ["action_"],
            "button": ["button_"],
            "cron": ["_cron_", "_scheduled_"],
        }
    )

    # Model attributes
    model_attributes: List[str] = field(
        default_factory=lambda: [
            "_name",
            "_inherit",
            "_inherits",
            "_description",
            "_table",
            "_sequence",
            "_sql_constraints",
            "_rec_name",
            "_order",
            "_auto",
            "_register",
            "_abstract",
            "_transient",
            "_date_name",
            "_fold_name",
            "_parent_name",
            "_parent_store",
            "_check_company_auto",
            "_check_company_domain",
        ]
    )

    # Import group patterns
    import_patterns: Dict[str, List[str]] = field(
        default_factory=lambda: {
            "python_stdlib": [],  # Will be populated from stdlib list
            "third_party": ["lxml", "psycopg2", "PIL", "werkzeug", "dateutil"],
            "odoo": ["odoo", "openerp"],
            "odoo_addons": ["odoo.addons", "openerp.addons"],
        }
    )

    # Header patterns for detection
    header_patterns: List[str] = field(
        default_factory=lambda: [
            "# -*- coding:",
            "# -*-coding:",
            "# coding:",
            "#!",
            "copyright",
            "license",
            "author",
            "flake8:",
            "pylint:",
            "type:",
            "mypy:",
            "fmt:",
            "isort:",
        ]
    )

    @classmethod
    def get_default(cls) -> "OdooConfig":
        """Get default Odoo configuration."""
        return cls()

    def get_version_enum(self) -> OdooVersion:
        """Get version as enum."""
        return OdooVersion.from_string(self.version)

    def is_odoo_field_type(self, name: str) -> bool:
        """Check if a name is an Odoo field type."""
        return name in self.field_types

    def is_api_decorator(self, decorator: str) -> bool:
        """Check if a decorator is an Odoo API decorator."""
        return any(api in decorator for api in self.api_decorators)

    def get_method_type(self, method_name: str) -> str:
        """Determine method type from its name."""
        for method_type, patterns in self.method_patterns.items():
            if any(pattern in method_name for pattern in patterns):
                return method_type
        return "other"

    def is_model_attribute(self, name: str) -> bool:
        """Check if a name is a model attribute."""
        return name in self.model_attributes

    def is_special_directory(self, dirname: str) -> bool:
        """Check if a directory is an Odoo special directory."""
        return dirname in self.special_dirs

    def should_skip_directory(self, dirname: str) -> bool:
        """Check if a directory should be skipped."""
        return dirname in self.skip_dirs
