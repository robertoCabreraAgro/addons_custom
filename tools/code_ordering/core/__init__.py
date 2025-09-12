"""
Core foundation modules for code ordering tools.

This package provides shared functionality for AST processing,
element extraction, and file operations.
"""

from .ast_processor import BaseASTProcessor
from .element_extractor import UnifiedElement, ElementExtractor, ElementType
from .file_operations import FileOperations
from .shared_cache import SharedCache
from .unified_cache import UnifiedCache, CacheCategory
from .base_patterns import Singleton, SingletonMeta, ConfigBase, setup_logging

__all__ = [
    "BaseASTProcessor",
    "UnifiedElement",
    "ElementExtractor",
    "ElementType",
    "FileOperations",
    "SharedCache",
    "UnifiedCache",
    "CacheCategory",
    "Singleton",
    "SingletonMeta",
    "ConfigBase",
    "setup_logging",
]
