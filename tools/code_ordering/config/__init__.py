"""
Configuration management for code ordering tools.

This package provides centralized configuration management
with support for different tool configurations.
"""

from .base import BaseConfig, ConfigManager
from .odoo_config import OdooConfig, OdooVersion
from .reorder_config import ReorderConfig
from .validation_config import ValidationConfig

__all__ = [
    "BaseConfig",
    "ConfigManager",
    "OdooConfig",
    "OdooVersion",
    "ReorderConfig",
    "ValidationConfig",
]
