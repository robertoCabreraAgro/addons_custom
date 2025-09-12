"""
Shared cache module - now redirects to unified cache.

This module is kept for backward compatibility but internally uses
the new UnifiedCache system.
"""

from .unified_cache import UnifiedCache


class SharedCache:
    """
    Legacy SharedCache interface redirecting to UnifiedCache.

    Maintained for backward compatibility.
    """

    def __init__(self):
        """Initialize with unified cache."""
        self._cache = UnifiedCache()

    def get_ast(self, content: str):
        """Get cached AST."""
        return self._cache.get_ast(content)

    def set_ast(self, content: str, tree, lines):
        """Set cached AST."""
        self._cache.set_ast(content, tree, lines)

    def get_file(self, filepath):
        """Get cached file."""
        return self._cache.get_file(filepath)

    def set_file(self, filepath, content):
        """Set cached file."""
        self._cache.set_file(filepath, content)

    def clear(self):
        """Clear all caches."""
        self._cache.clear()

    def get_stats(self):
        """Get cache statistics."""
        return self._cache.get_stats()
