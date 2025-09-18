#!/usr/bin/env python3
"""
Base mixins and shared utilities for Odoo code analysis tools.

This module provides common functionality used across multiple tools to reduce
code duplication and ensure consistency.
"""

import ast
import json
import logging
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================
# ODOO CONSTANTS
# ============================================================


class OdooConstants:
    """Centralized Odoo-specific constants and patterns."""

    # Field types recognized in Odoo
    FIELD_TYPES = {
        "Char",
        "Text",
        "Html",
        "Integer",
        "Float",
        "Monetary",
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
        "Many2oneReference",
    }

    # Model base classes
    MODEL_BASES = ["Model", "TransientModel", "AbstractModel"]

    # Model attributes in preferred order
    MODEL_ATTRIBUTES = [
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
        "_order",
        "_auto",
        "_abstract",
        "_check_company_auto",
        "_custom",
    ]

    # SQL constraints pattern
    SQL_CONSTRAINTS = ["_sql_constraints"]

    # Common method decorators
    DECORATORS = {
        "api.depends",
        "api.depends_context",
        "api.onchange",
        "api.constrains",
        "api.model",
        "api.model_create_multi",
        "api.autovacuum",
        "api.ondelete",
    }


# ============================================================
# AST ANALYSIS MIXINS
# ============================================================


class OdooASTMixin:
    """Mixin for common AST analysis operations on Odoo code."""

    def is_odoo_model(self, node: ast.ClassDef) -> bool:
        """Check if a class definition is an Odoo model.

        Args:
            node: AST ClassDef node to check

        Returns:
            bool: True if the class inherits from an Odoo model base
        """
        for base in node.bases:
            if isinstance(base, ast.Attribute):
                if base.attr in OdooConstants.MODEL_BASES:
                    return True
                # Check for models.Model pattern
                if (
                    isinstance(base.value, ast.Name)
                    and base.value.id == "models"
                    and base.attr in OdooConstants.MODEL_BASES
                ):
                    return True
        return False

    def get_model_name(self, node: ast.ClassDef) -> str | None:
        """Extract model name from _name or _inherit attributes.

        Args:
            node: AST ClassDef node of an Odoo model

        Returns:
            str: Model name if found, None otherwise
        """
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        if target.id in ["_name", "_inherit"]:
                            if isinstance(item.value, ast.Constant):
                                return item.value.value
                            elif isinstance(item.value, ast.Str):  # Python < 3.8
                                return item.value.s
        return None

    def is_field_assignment(self, node: ast.Assign) -> bool:
        """Check if an assignment is a field definition.

        Args:
            node: AST Assign node to check

        Returns:
            bool: True if this is a fields.* assignment
        """
        if isinstance(node.value, ast.Call):
            if isinstance(node.value.func, ast.Attribute):
                return node.value.func.attr in OdooConstants.FIELD_TYPES
        return False

    def get_field_type(self, node: ast.Assign) -> str | None:
        """Extract field type from a field assignment.

        Args:
            node: AST Assign node of a field definition

        Returns:
            str: Field type name if found, None otherwise
        """
        if isinstance(node.value, ast.Call):
            if isinstance(node.value.func, ast.Attribute):
                if node.value.func.attr in OdooConstants.FIELD_TYPES:
                    return node.value.func.attr
        return None

    def get_field_name(self, node: ast.Assign) -> str | None:
        """Extract field name from a field assignment.

        Args:
            node: AST Assign node of a field definition

        Returns:
            str: Field name if found, None otherwise
        """
        if node.targets and isinstance(node.targets[0], ast.Name):
            return node.targets[0].id
        return None

    def is_model_attribute(self, node: ast.Assign) -> bool:
        """Check if an assignment is a model attribute (like _name, _inherit).

        Args:
            node: AST Assign node to check

        Returns:
            bool: True if this is a model attribute assignment
        """
        if node.targets and isinstance(node.targets[0], ast.Name):
            return node.targets[0].id in OdooConstants.MODEL_ATTRIBUTES
        return False


# ============================================================
# FILE OPERATION MIXINS
# ============================================================


class BackupMixin:
    """Mixin for file backup operations."""

    def create_backup(self, filepath: Path, backup_dir: Path | None = None) -> Path:
        """Create a backup of a file.

        Args:
            filepath: Path to the file to backup
            backup_dir: Optional directory for backups, uses default if None

        Returns:
            Path: Path to the backup file
        """
        if not filepath.exists():
            raise FileNotFoundError(f"Cannot backup non-existent file: {filepath}")

        if backup_dir is None:
            backup_dir = Path(f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

        backup_dir = Path(backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Preserve directory structure in backup
        relative_path = filepath.name
        if filepath.parent != Path("."):
            relative_path = (
                filepath.relative_to(Path.cwd()) if filepath.is_absolute() else filepath
            )

        backup_path = backup_dir / relative_path
        backup_path.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(filepath, backup_path)
        logger.info(f"Created backup: {backup_path}")

        return backup_path

    def restore_from_backup(
        self, backup_path: Path, original_path: Path | None = None
    ) -> bool:
        """Restore a file from backup.

        Args:
            backup_path: Path to the backup file
            original_path: Optional original path, extracted from backup if None

        Returns:
            bool: True if restoration successful
        """
        if not backup_path.exists():
            logger.error(f"Backup file not found: {backup_path}")
            return False

        if original_path is None:
            # Try to extract original path from backup structure
            original_path = Path(backup_path.name)

        try:
            shutil.copy2(backup_path, original_path)
            logger.info(f"Restored {original_path} from backup")
            return True
        except Exception as e:
            logger.error(f"Error restoring from backup: {e}")
            return False


# ============================================================
# CONFIGURATION MIXINS
# ============================================================


@dataclass
class BaseConfig:
    """Base configuration class with common settings."""

    # File operations
    create_backup: bool = True
    dry_run: bool = False

    # Formatting
    add_section_headers: bool = True
    line_length: int = 88

    # Processing
    recursive: bool = False
    verbose: bool = False

    @classmethod
    def from_json(cls, filepath: Path) -> "BaseConfig":
        """Load configuration from JSON file.

        Args:
            filepath: Path to JSON configuration file

        Returns:
            BaseConfig: Configuration instance with values from file
        """
        if not filepath.exists():
            return cls()

        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            # Filter only valid fields for this class
            valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
            filtered_data = {k: v for k, v in data.items() if k in valid_fields}

            return cls(**filtered_data)
        except Exception as e:
            logger.warning(f"Error loading config from {filepath}: {e}")
            return cls()

    def to_json(self, filepath: Path) -> None:
        """Save configuration to JSON file.

        Args:
            filepath: Path where to save the JSON file
        """
        data = {
            field.name: getattr(self, field.name)
            for field in self.__dataclass_fields__.values()
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Configuration saved to {filepath}")


# ============================================================
# NAMING UTILITIES
# ============================================================


class NamingUtilsMixin:
    """Mixin for common naming convention utilities."""

    @staticmethod
    def snake_case(name: str) -> str:
        """Convert CamelCase to snake_case.

        Args:
            name: String in CamelCase or mixed case

        Returns:
            str: String in snake_case
        """
        # Insert underscore before uppercase letters preceded by lowercase
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        # Insert underscore before uppercase letters preceded by lowercase or numbers
        s2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1)
        return s2.lower()

    @staticmethod
    def is_private(name: str) -> bool:
        """Check if a name indicates a private member.

        Args:
            name: Variable or method name

        Returns:
            bool: True if name starts with underscore (private)
        """
        return name.startswith("_") and not name.startswith("__")

    @staticmethod
    def is_dunder(name: str) -> bool:
        """Check if a name is a dunder (double underscore) method.

        Args:
            name: Method name

        Returns:
            bool: True if name starts and ends with double underscores
        """
        return name.startswith("__") and name.endswith("__")

    @staticmethod
    def normalize_module_name(name: str) -> str:
        """Normalize module name to standard format.

        Args:
            name: Module name (possibly with dots)

        Returns:
            str: Normalized module name with underscores
        """
        return name.replace(".", "_").replace("-", "_").lower()


# ============================================================
# REPORT GENERATION MIXINS
# ============================================================


class ReportMixin:
    """Mixin for generating analysis reports."""

    def generate_json_report(self, data: dict, filepath: Path) -> None:
        """Generate a JSON report file.

        Args:
            data: Dictionary of report data
            filepath: Path where to save the report
        """
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            **data,
        }

        with open(filepath, "w") as f:
            json.dump(report_data, f, indent=2, default=str)

        logger.info(f"Report saved to {filepath}")

    def generate_text_report(
        self,
        title: str,
        sections: dict[str, list[str]],
        filepath: Path | None = None,
    ) -> str:
        """Generate a formatted text report.

        Args:
            title: Report title
            sections: Dictionary of section names to content lines
            filepath: Optional path to save the report

        Returns:
            str: Formatted report text
        """
        lines = []
        lines.append(title)
        lines.append("=" * len(title))
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        for section_name, section_lines in sections.items():
            lines.append(section_name)
            lines.append("-" * len(section_name))
            lines.extend(section_lines)
            lines.append("")

        report_text = "\n".join(lines)

        if filepath:
            with open(filepath, "w") as f:
                f.write(report_text)
            logger.info(f"Text report saved to {filepath}")

        return report_text


# ============================================================
# MODULE PATH UTILITIES
# ============================================================


class ModulePathMixin:
    """Mixin for handling Odoo module paths."""

    @staticmethod
    def find_module_root(filepath: Path) -> Path | None:
        """Find the root directory of an Odoo module.

        Args:
            filepath: Path to a file within a module

        Returns:
            Path: Root directory of the module if found, None otherwise
        """
        current = filepath.parent if filepath.is_file() else filepath

        while current != current.parent:
            if (current / "__manifest__.py").exists() or (
                current / "__openerp__.py"
            ).exists():
                return current
            current = current.parent

        return None

    @staticmethod
    def get_module_name(filepath: Path) -> str | None:
        """Extract module name from a file path.

        Args:
            filepath: Path to a file within a module

        Returns:
            str: Module name if found, None otherwise
        """
        module_root = ModulePathMixin.find_module_root(filepath)
        return module_root.name if module_root else None

    @staticmethod
    def find_addon_paths(base_path: Path) -> list[Path]:
        """Find all addon directories from a base path.

        Args:
            base_path: Base Odoo installation path

        Returns:
            list[Path]: List of existing addon directories
        """
        potential_paths = [
            base_path / "addons",
            base_path / "addons_enterprise",
            base_path / "addons_custom",
            base_path / "enterprise",
            base_path / "custom",
        ]

        # Also check parent directory for enterprise
        if base_path.parent:
            potential_paths.extend(
                [
                    base_path.parent / "enterprise",
                    base_path.parent / "addons_enterprise",
                ]
            )

        return [p for p in potential_paths if p.exists() and p.is_dir()]


# ============================================================
# DECORATOR UTILITIES
# ============================================================


class DecoratorMixin:
    """Mixin for handling Python decorators in AST."""

    @staticmethod
    def get_decorator_names(node: ast.FunctionDef) -> list[str]:
        """Extract decorator names from a function node.

        Args:
            node: AST FunctionDef node

        Returns:
            list[str]: List of decorator names
        """
        decorator_names = []

        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                decorator_names.append(decorator.id)
            elif isinstance(decorator, ast.Attribute):
                parts = []
                current = decorator
                while isinstance(current, ast.Attribute):
                    parts.append(current.attr)
                    current = current.value
                if isinstance(current, ast.Name):
                    parts.append(current.id)
                decorator_names.append(".".join(reversed(parts)))
            elif isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute):
                    decorator_names.append(
                        f"{decorator.func.value.id}.{decorator.func.attr}"
                        if isinstance(decorator.func.value, ast.Name)
                        else decorator.func.attr
                    )

        return decorator_names

    @staticmethod
    def has_decorator(node: ast.FunctionDef, decorator_name: str) -> bool:
        """Check if a function has a specific decorator.

        Args:
            node: AST FunctionDef node
            decorator_name: Name of decorator to check for

        Returns:
            bool: True if decorator is present
        """
        decorator_names = DecoratorMixin.get_decorator_names(node)
        return decorator_name in decorator_names or any(
            d.endswith(f".{decorator_name}") for d in decorator_names
        )
