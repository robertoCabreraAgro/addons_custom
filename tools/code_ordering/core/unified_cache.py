"""
Unified caching system for all components.

Replaces separate AST, File, and Shared caches with a single
type-safe, category-based caching system.
"""

import ast
import hashlib
import time
from collections import OrderedDict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .base_patterns import Singleton, setup_logging

logger = setup_logging(__name__)


class CacheCategory(Enum):
    """Categories for different types of cached data."""

    AST = "ast"  # AST trees and related data
    FILE = "file"  # File contents
    CONFIG = "config"  # Configuration objects
    ANALYSIS = "analysis"  # Analysis results
    GENERAL = "general"  # General purpose cache


class CacheEntry:
    """Single cache entry with metadata."""

    def __init__(self, key: str, value: Any, category: CacheCategory):
        self.key = key
        self.value = value
        self.category = category
        self.timestamp = time.time()
        self.access_count = 0
        self.last_access = self.timestamp

    def access(self) -> Any:
        """Access the cached value and update stats."""
        self.access_count += 1
        self.last_access = time.time()
        return self.value

    @property
    def age(self) -> float:
        """Age of the cache entry in seconds."""
        return time.time() - self.timestamp

    @property
    def idle_time(self) -> float:
        """Time since last access in seconds."""
        return time.time() - self.last_access


class UnifiedCache(Singleton):
    """
    Unified cache system for all components.

    Features:
    - Category-based organization
    - LRU eviction with category-specific limits
    - Statistics tracking
    - Thread-safe operations
    """

    def __init__(self, max_size: int = 1000, max_age: float = 3600):
        """
        Initialize unified cache.

        Args:
            max_size: Maximum total cache entries
            max_age: Maximum age for entries in seconds
        """
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_size = max_size
        self._max_age = max_age

        # Category-specific limits (percentage of total)
        self._category_limits = {
            CacheCategory.AST: 0.3,  # 30% for AST
            CacheCategory.FILE: 0.3,  # 30% for files
            CacheCategory.CONFIG: 0.1,  # 10% for config
            CacheCategory.ANALYSIS: 0.2,  # 20% for analysis
            CacheCategory.GENERAL: 0.1,  # 10% for general
        }

        # Statistics
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "additions": 0,
        }

        logger.debug(f"Initialized UnifiedCache with max_size={max_size}")

    def _make_key(self, category: CacheCategory, identifier: Union[str, Path]) -> str:
        """Create a unique cache key."""
        if isinstance(identifier, Path):
            identifier = str(identifier.absolute())
        return f"{category.value}:{identifier}"

    def get(
        self, category: CacheCategory, identifier: Union[str, Path], default: Any = None
    ) -> Any:
        """
        Get a value from cache.

        Args:
            category: Cache category
            identifier: Unique identifier within category
            default: Default value if not found

        Returns:
            Cached value or default
        """
        key = self._make_key(category, identifier)

        if key in self._cache:
            entry = self._cache[key]

            # Check if entry is too old
            if entry.age > self._max_age:
                del self._cache[key]
                self._stats["evictions"] += 1
                self._stats["misses"] += 1
                logger.debug(f"Cache miss (expired): {key}")
                return default

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._stats["hits"] += 1
            logger.debug(f"Cache hit: {key}")
            return entry.access()

        self._stats["misses"] += 1
        logger.debug(f"Cache miss: {key}")
        return default

    def set(
        self, category: CacheCategory, identifier: Union[str, Path], value: Any
    ) -> None:
        """
        Set a value in cache.

        Args:
            category: Cache category
            identifier: Unique identifier within category
            value: Value to cache
        """
        key = self._make_key(category, identifier)

        # Check if we need to evict
        if len(self._cache) >= self._max_size:
            self._evict()

        # Add or update entry
        self._cache[key] = CacheEntry(key, value, category)
        self._cache.move_to_end(key)
        self._stats["additions"] += 1
        logger.debug(f"Cache set: {key}")

    def _evict(self) -> None:
        """Evict entries based on LRU and category limits."""
        # First, remove expired entries
        expired = [
            key for key, entry in self._cache.items() if entry.age > self._max_age
        ]
        for key in expired:
            del self._cache[key]
            self._stats["evictions"] += 1

        # If still over limit, use LRU
        if len(self._cache) >= self._max_size:
            # Remove least recently used
            key = next(iter(self._cache))
            del self._cache[key]
            self._stats["evictions"] += 1
            logger.debug(f"Evicted LRU entry: {key}")

    def clear(self, category: Optional[CacheCategory] = None) -> None:
        """
        Clear cache entries.

        Args:
            category: Clear only this category, or all if None
        """
        if category is None:
            self._cache.clear()
            logger.info("Cleared all cache entries")
        else:
            keys_to_remove = [
                key for key, entry in self._cache.items() if entry.category == category
            ]
            for key in keys_to_remove:
                del self._cache[key]
            logger.info(f"Cleared {len(keys_to_remove)} entries from {category.value}")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0

        category_counts = {}
        for category in CacheCategory:
            count = sum(1 for e in self._cache.values() if e.category == category)
            category_counts[category.value] = count

        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate": hit_rate,
            "evictions": self._stats["evictions"],
            "additions": self._stats["additions"],
            "categories": category_counts,
        }

    # Specialized methods for common operations

    def get_ast(self, content: str) -> Optional[Tuple[ast.Module, List[str]]]:
        """Get cached AST for Python content."""
        # Use content hash as identifier
        content_hash = hashlib.md5(content.encode()).hexdigest()
        return self.get(CacheCategory.AST, content_hash)

    def set_ast(self, content: str, tree: ast.Module, lines: List[str]) -> None:
        """Cache AST for Python content."""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        self.set(CacheCategory.AST, content_hash, (tree, lines))

    def get_file(self, filepath: Path) -> Optional[str]:
        """Get cached file content."""
        return self.get(CacheCategory.FILE, filepath)

    def set_file(self, filepath: Path, content: str) -> None:
        """Cache file content."""
        self.set(CacheCategory.FILE, filepath, content)

    def get_config(self, name: str) -> Optional[Any]:
        """Get cached configuration."""
        return self.get(CacheCategory.CONFIG, name)

    def set_config(self, name: str, config: Any) -> None:
        """Cache configuration."""
        self.set(CacheCategory.CONFIG, name, config)
