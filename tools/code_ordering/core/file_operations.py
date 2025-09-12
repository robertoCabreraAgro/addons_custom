"""
Centralized file operations with caching.

This module provides consistent file I/O operations across all tools,
with built-in caching to avoid redundant reads.
"""

import hashlib
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from .base_patterns import setup_logging
from .unified_cache import CacheCategory, UnifiedCache

logger = setup_logging(__name__)


class FileOperations:
    """
    Centralized file operations with consistent error handling.

    This class provides all file I/O operations needed by the tools,
    with built-in caching and error handling.
    """

    ENCODING = "utf-8"
    BACKUP_SUFFIX = ".bak"

    def __init__(self):
        """Initialize with unified cache."""
        self._cache = UnifiedCache()
        self.created_backups = []  # Track created backups for cleanup

    @classmethod
    def read_file(cls, filepath: Path, use_cache: bool = True) -> str:
        """
        Read file content with optional caching.

        Args:
            filepath: Path to the file
            use_cache: Whether to use caching

        Returns:
            File content as string

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If file cannot be read
        """
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        if not filepath.is_file():
            raise IOError(f"Not a file: {filepath}")

        cache = UnifiedCache()

        # Check cache first
        if use_cache:
            # Check file modification time
            try:
                mtime = filepath.stat().st_mtime
                cache_key = f"{filepath}:{mtime}"
                cached = cache.get(CacheCategory.FILE, cache_key)
                if cached is not None:
                    logger.debug(f"Using cached content for {filepath}")
                    return cached
            except (OSError, IOError):
                pass

        # Read file
        try:
            content = filepath.read_text(encoding=cls.ENCODING)
            logger.debug(f"Read {len(content)} bytes from {filepath}")

            # Cache content with mtime
            if use_cache:
                try:
                    mtime = filepath.stat().st_mtime
                    cache_key = f"{filepath}:{mtime}"
                    cache.set(CacheCategory.FILE, cache_key, content)
                except (OSError, IOError):
                    pass

            return content

        except UnicodeDecodeError as e:
            logger.error(f"Encoding error reading {filepath}: {e}")
            raise IOError(f"Cannot decode {filepath} as {cls.ENCODING}")
        except Exception as e:
            logger.error(f"Error reading {filepath}: {e}")
            raise IOError(f"Failed to read {filepath}: {e}")

    @classmethod
    def write_file(cls, filepath: Path, content: str, create_dirs: bool = True) -> None:
        """
        Write content to file with consistent error handling.

        Args:
            filepath: Path to the file
            content: Content to write
            create_dirs: Whether to create parent directories

        Raises:
            IOError: If file cannot be written
        """
        try:
            # Create parent directories if needed
            if create_dirs and not filepath.parent.exists():
                filepath.parent.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Created directory {filepath.parent}")

            # Write file
            filepath.write_text(content, encoding=cls.ENCODING)
            logger.debug(f"Wrote {len(content)} bytes to {filepath}")

            # Note: Cache will be invalidated on next read due to mtime change

        except Exception as e:
            logger.error(f"Error writing {filepath}: {e}")
            raise IOError(f"Failed to write {filepath}: {e}")

    def create_backup(self, filepath: Path, suffix: Optional[str] = None) -> Path:
        """
        Create a backup of a file.

        Args:
            filepath: Path to the file to backup
            suffix: Custom suffix for backup (default: .bak)

        Returns:
            Path to the backup file

        Raises:
            IOError: If backup cannot be created
        """
        if not filepath.exists():
            raise FileNotFoundError(f"Cannot backup non-existent file: {filepath}")

        suffix = suffix or self.BACKUP_SUFFIX
        backup_path = filepath.with_suffix(filepath.suffix + suffix)

        try:
            shutil.copy2(filepath, backup_path)
            self.created_backups.append(backup_path)  # Track for cleanup
            logger.info(f"Created backup: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            raise IOError(f"Failed to backup {filepath}: {e}")

    @classmethod
    def should_skip(cls, filepath: Path, skip_dirs: List[str]) -> bool:
        """
        Check if a file should be skipped based on directory patterns.

        Args:
            filepath: Path to check
            skip_dirs: List of directory names to skip

        Returns:
            True if file should be skipped
        """
        # Check if any parent directory is in skip list
        for parent in filepath.parents:
            if parent.name in skip_dirs:
                return True
            # Also check for common Python directories to skip
            if parent.name in ["__pycache__", ".git", ".venv", "venv", ".pytest_cache"]:
                return True

        # Skip backup files
        if filepath.suffix in [".bak", ".pyc", ".pyo"]:
            return True

        # Skip __pycache__ directories
        if "__pycache__" in str(filepath):
            return True

        return False

    @classmethod
    def restore_backup(cls, filepath: Path, suffix: Optional[str] = None) -> None:
        """
        Restore a file from backup.

        Args:
            filepath: Path to the file to restore
            suffix: Custom suffix for backup (default: .bak)

        Raises:
            FileNotFoundError: If backup doesn't exist
            IOError: If restore fails
        """
        suffix = suffix or cls.BACKUP_SUFFIX
        backup_path = filepath.with_suffix(filepath.suffix + suffix)

        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_path}")

        try:
            shutil.copy2(backup_path, filepath)
            logger.info(f"Restored from backup: {filepath}")
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            raise IOError(f"Failed to restore {filepath}: {e}")

    @classmethod
    def list_python_files(cls, directory: Path, recursive: bool = True) -> List[Path]:
        """
        List all Python files in a directory.

        Args:
            directory: Directory to search
            recursive: Whether to search recursively

        Returns:
            List of Python file paths
        """
        if not directory.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")

        pattern = "**/*.py" if recursive else "*.py"
        files = sorted(directory.glob(pattern))

        # Filter out common non-source files
        skip_patterns = {"__pycache__", ".git", ".venv", "venv", "env"}
        files = [f for f in files if not any(skip in f.parts for skip in skip_patterns)]

        logger.debug(f"Found {len(files)} Python files in {directory}")
        return files

    @classmethod
    def get_file_stats(cls, filepath: Path) -> Dict[str, any]:
        """
        Get statistics about a file.

        Args:
            filepath: Path to the file

        Returns:
            Dictionary with file statistics
        """
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        stats = filepath.stat()
        content = cls.read_file(filepath, use_cache=False)
        lines = content.splitlines()

        return {
            "path": str(filepath),
            "size_bytes": stats.st_size,
            "modified_time": stats.st_mtime,
            "lines": len(lines),
            "characters": len(content),
            "is_executable": filepath.is_file() and stats.st_mode & 0o111,
        }

    @classmethod
    def ensure_directory(cls, directory: Path) -> None:
        """
        Ensure a directory exists, creating if necessary.

        Args:
            directory: Directory path
        """
        directory.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured directory exists: {directory}")

    @classmethod
    def copy_file(
        cls, source: Path, destination: Path, overwrite: bool = False
    ) -> None:
        """
        Copy a file to a new location.

        Args:
            source: Source file path
            destination: Destination file path
            overwrite: Whether to overwrite existing file

        Raises:
            FileExistsError: If destination exists and overwrite is False
            IOError: If copy fails
        """
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source}")

        if destination.exists() and not overwrite:
            raise FileExistsError(f"Destination already exists: {destination}")

        try:
            shutil.copy2(source, destination)
            logger.debug(f"Copied {source} to {destination}")
        except Exception as e:
            logger.error(f"Failed to copy file: {e}")
            raise IOError(f"Failed to copy {source} to {destination}: {e}")

    @classmethod
    def delete_file(cls, filepath: Path, safe: bool = True) -> None:
        """
        Delete a file.

        Args:
            filepath: File to delete
            safe: If True, create backup before deletion

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If deletion fails
        """
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        try:
            if safe:
                cls.create_backup(filepath)

            filepath.unlink()
            logger.info(f"Deleted file: {filepath}")
        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
            raise IOError(f"Failed to delete {filepath}: {e}")

    @classmethod
    def compute_file_hash(cls, filepath: Path, algorithm: str = "md5") -> str:
        """
        Compute hash of a file.

        Args:
            filepath: File to hash
            algorithm: Hash algorithm (md5, sha1, sha256)

        Returns:
            Hex digest of the file hash
        """
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        hash_func = getattr(hashlib, algorithm)()

        with filepath.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_func.update(chunk)

        return hash_func.hexdigest()

    @classmethod
    def find_files(cls, directory: Path, pattern: str) -> List[Path]:
        """
        Find files matching a pattern.

        Args:
            directory: Directory to search
            pattern: Glob pattern

        Returns:
            List of matching file paths
        """
        if not directory.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")

        matches = sorted(directory.glob(pattern))
        logger.debug(f"Found {len(matches)} files matching '{pattern}' in {directory}")
        return matches

    def cleanup_backups(self) -> None:
        """Delete all created backup files."""
        for backup_path in self.created_backups:
            if backup_path.exists():
                backup_path.unlink()
                logger.debug(f"Deleted backup: {backup_path}")
        self.created_backups.clear()
        logger.info("Cleaned up backup files")
