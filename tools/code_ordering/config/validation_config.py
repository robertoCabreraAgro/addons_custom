"""
Configuration for validation operations.

This module provides configuration specific to the validation tool.
"""

from dataclasses import dataclass, field
from typing import Dict, List

from .base import BaseConfig


@dataclass
class ValidationConfig(BaseConfig):
    """
    Configuration for validation operations.

    Controls how code validation is performed.
    """

    # Validation strictness
    strict_mode: bool = False
    allow_added_elements: bool = True
    allow_removed_elements: bool = False
    allow_order_changes: bool = True

    # Element validation
    validate_imports: bool = True
    validate_classes: bool = True
    validate_methods: bool = True
    validate_fields: bool = True
    validate_functions: bool = True
    validate_variables: bool = True
    validate_decorators: bool = True
    validate_docstrings: bool = False

    # Comparison options
    ignore_whitespace: bool = True
    ignore_comments: bool = True
    ignore_docstrings: bool = True
    ignore_type_hints: bool = False
    case_sensitive: bool = True

    # Reporting
    report_format: str = "text"  # text, json, html
    show_line_numbers: bool = True
    max_diff_lines: int = 50
    context_lines: int = 3

    # Element categories to validate
    element_categories: List[str] = field(
        default_factory=lambda: [
            "imports",
            "classes",
            "methods",
            "fields",
            "functions",
            "variables",
            "properties",
            "decorators",
        ]
    )

    # Ignore patterns
    ignore_patterns: Dict[str, List[str]] = field(
        default_factory=lambda: {
            "methods": ["__.*__"],  # Ignore dunder methods
            "fields": ["_.*"],  # Ignore private fields
            "variables": ["_.*"],  # Ignore private variables
        }
    )

    # Validation rules
    rules: Dict[str, bool] = field(
        default_factory=lambda: {
            "require_all_imports": True,
            "require_all_classes": True,
            "require_all_methods": True,
            "require_all_fields": True,
            "require_same_decorators": False,
            "require_same_docstrings": False,
            "require_same_order": False,
            "allow_new_elements": True,
            "allow_renamed_elements": False,
        }
    )

    # Performance settings
    use_cache: bool = True
    parallel_validation: bool = False
    max_workers: int = 4

    # Output settings
    verbose: bool = False
    quiet: bool = False
    color_output: bool = True

    # Thresholds
    similarity_threshold: float = 0.95  # For fuzzy matching
    max_validation_time_seconds: int = 300  # 5 minutes

    @classmethod
    def get_default(cls) -> "ValidationConfig":
        """Get default validation configuration."""
        return cls()

    def should_validate_element(self, element_type: str) -> bool:
        """Check if an element type should be validated."""
        validation_map = {
            "imports": self.validate_imports,
            "classes": self.validate_classes,
            "methods": self.validate_methods,
            "fields": self.validate_fields,
            "functions": self.validate_functions,
            "variables": self.validate_variables,
            "decorators": self.validate_decorators,
            "docstrings": self.validate_docstrings,
        }
        return validation_map.get(element_type, True)

    def should_ignore_element(self, element_name: str, element_type: str) -> bool:
        """Check if an element should be ignored based on patterns."""
        if element_type in self.ignore_patterns:
            import re

            for pattern in self.ignore_patterns[element_type]:
                if re.match(pattern, element_name):
                    return True
        return False

    def get_validation_rule(self, rule_name: str) -> bool:
        """Get a specific validation rule value."""
        return self.rules.get(rule_name, False)

    def set_strict_mode(self) -> None:
        """Enable strict validation mode."""
        self.strict_mode = True
        self.allow_added_elements = False
        self.allow_removed_elements = False
        self.allow_order_changes = False
        self.rules["require_same_decorators"] = True
        self.rules["require_same_order"] = True
        self.rules["allow_new_elements"] = False

    def set_lenient_mode(self) -> None:
        """Enable lenient validation mode."""
        self.strict_mode = False
        self.allow_added_elements = True
        self.allow_removed_elements = True
        self.allow_order_changes = True
        self.rules["require_same_decorators"] = False
        self.rules["require_same_order"] = False
        self.rules["allow_new_elements"] = True
