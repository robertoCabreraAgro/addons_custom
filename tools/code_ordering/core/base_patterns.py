"""
Base patterns and utilities for the codebase.

Provides reusable patterns like Singleton metaclass and base classes
to eliminate redundancy across modules.
"""

import logging
from abc import ABC, ABCMeta
from typing import Any, Dict, Type

logger = logging.getLogger(__name__)


class SingletonMeta(ABCMeta):
    """
    Metaclass that creates singleton instances.

    Classes using this metaclass will only have one instance.
    Thread-safe implementation using __call__ method.
    """

    _instances: Dict[Type, Any] = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
            logger.debug(f"Created singleton instance of {cls.__name__}")
        return cls._instances[cls]

    @classmethod
    def clear_all(mcs):
        """Clear all singleton instances (useful for testing)."""
        mcs._instances.clear()


class Singleton(ABC, metaclass=SingletonMeta):
    """
    Base class for singleton objects.

    Inherit from this class to make any class a singleton.
    """

    pass


class ConfigBase(ABC):
    """
    Base class for configuration objects with common patterns.
    """

    @classmethod
    def get_default(cls):
        """Get default configuration instance."""
        return cls()

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        result = {}
        for key, value in self.__dict__.items():
            if not key.startswith("_"):
                if hasattr(value, "to_dict"):
                    result[key] = value.to_dict()
                elif isinstance(value, (list, dict, str, int, float, bool, type(None))):
                    result[key] = value
                else:
                    result[key] = str(value)
        return result

    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update configuration from dictionary."""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)


def setup_logging(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Set up logging for a module.

    Args:
        name: Logger name (usually __name__)
        level: Logging level

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(level)
    return logger
