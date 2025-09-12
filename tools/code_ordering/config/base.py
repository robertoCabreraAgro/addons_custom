"""
Base configuration classes and manager.

This module provides the foundation for all configuration management.
"""

import json
import logging

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T", bound="BaseConfig")


@dataclass
class BaseConfig(ABC):
    """
    Abstract base class for all configurations.

    Provides common functionality for configuration management.
    """

    @classmethod
    @abstractmethod
    def get_default(cls) -> "BaseConfig":
        """Get default configuration."""
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert configuration to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Create configuration from dictionary."""
        return cls(**data)

    @classmethod
    def from_json(cls: Type[T], json_str: str) -> T:
        """Create configuration from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def from_file(cls: Type[T], filepath: Path) -> T:
        """Load configuration from file."""
        if not filepath.exists():
            logger.warning(f"Config file not found: {filepath}, using defaults")
            return cls.get_default()

        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load config from {filepath}: {e}")
            return cls.get_default()

    def save(self, filepath: Path) -> None:
        """Save configuration to file."""
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w") as f:
                json.dump(self.to_dict(), f, indent=2)
            logger.info(f"Saved configuration to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save config to {filepath}: {e}")
            raise

    def update(self, **kwargs) -> None:
        """Update configuration fields."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                logger.warning(f"Unknown config field: {key}")


class ConfigManager:
    """
    Centralized configuration manager.

    Manages all configuration types and provides a unified interface.
    """

    _instance = None
    _configs: Dict[str, BaseConfig] = {}
    _config_classes: Dict[str, Type[BaseConfig]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register_config(cls, name: str, config_class: Type[BaseConfig]) -> None:
        """
        Register a configuration class.

        Args:
            name: Configuration name
            config_class: Configuration class type
        """
        cls._config_classes[name] = config_class
        logger.debug(f"Registered config type: {name}")

    @classmethod
    def get_config(cls, name: str) -> BaseConfig:
        """
        Get configuration by name.

        Args:
            name: Configuration name

        Returns:
            Configuration instance
        """
        if name not in cls._configs:
            if name in cls._config_classes:
                cls._configs[name] = cls._config_classes[name].get_default()
            else:
                raise ValueError(f"Unknown configuration type: {name}")

        return cls._configs[name]

    @classmethod
    def set_config(cls, name: str, config: BaseConfig) -> None:
        """
        Set configuration.

        Args:
            name: Configuration name
            config: Configuration instance
        """
        cls._configs[name] = config
        logger.debug(f"Set config for {name}")

    @classmethod
    def load_config(cls, name: str, filepath: Path) -> BaseConfig:
        """
        Load configuration from file.

        Args:
            name: Configuration name
            filepath: Path to configuration file

        Returns:
            Loaded configuration
        """
        if name not in cls._config_classes:
            raise ValueError(f"Unknown configuration type: {name}")

        config_class = cls._config_classes[name]
        config = config_class.from_file(filepath)
        cls._configs[name] = config

        return config

    @classmethod
    def save_config(cls, name: str, filepath: Path) -> None:
        """
        Save configuration to file.

        Args:
            name: Configuration name
            filepath: Path to save to
        """
        if name not in cls._configs:
            raise ValueError(f"No configuration set for: {name}")

        cls._configs[name].save(filepath)

    @classmethod
    def reset_config(cls, name: Optional[str] = None) -> None:
        """
        Reset configuration to defaults.

        Args:
            name: Configuration name, or None for all
        """
        if name is None:
            # Reset all
            for config_name in cls._config_classes:
                cls._configs[config_name] = cls._config_classes[
                    config_name
                ].get_default()
            logger.info("Reset all configurations to defaults")
        else:
            if name in cls._config_classes:
                cls._configs[name] = cls._config_classes[name].get_default()
                logger.info(f"Reset {name} configuration to defaults")
            else:
                raise ValueError(f"Unknown configuration type: {name}")

    @classmethod
    def get_all_configs(cls) -> Dict[str, BaseConfig]:
        """Get all registered configurations."""
        return cls._configs.copy()
