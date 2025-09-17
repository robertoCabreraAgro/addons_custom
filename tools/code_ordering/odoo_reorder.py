#!/usr/bin/env python3
"""
Odoo Source Code Reorganizer
Author: Agromarin Tools
Version: 1.0.0
"""

import argparse
import ast
from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
import shutil
import sys

from core.ordering import Ordering


try:
    import black
except ImportError:
    print("Error: Black is not installed. Please install it with: pip install black")
    sys.exit(1)

try:
    import isort
except ImportError:
    print("Error: isort is not installed. Please install it with: pip install isort")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================


@dataclass
class Config:
    """Configuration for code ordering operations.

    This dataclass holds all configuration options for the Odoo code reorganizer.
    It can be instantiated with defaults, loaded from a JSON file, or have its
    values overridden via command-line arguments.

    Attributes:
        field_strategy: Strategy for ordering fields ('semantic', 'type', or 'strict')
        add_section_headers: Whether to add comment headers between sections
        use_black: Whether to format output with Black formatter
        line_length: Maximum line length for Black formatting
        string_normalization: Whether Black should normalize string quotes
        magic_trailing_comma: Whether Black should respect trailing commas
        create_backup: Whether to create .bak files before modifying
        dry_run: Whether to preview changes without writing files
        recursive: Whether to process directories recursively
        method_groups: Ordered list of method categories for organization
    """

    # Reorder Settings
    field_strategy: str = "semantic"  # semantic, type, or strict
    add_section_headers: bool = True

    # Formatting Settings
    line_length: int = 88
    magic_trailing_comma: bool = True

    # File Operations
    create_backup: bool = True
    dry_run: bool = False
    recursive: bool = False

    @classmethod
    def from_file(cls, filepath: Path) -> "Config":
        """Load configuration from JSON file.

        Args:
            filepath: Path to JSON configuration file

        Returns:
            Config: Configuration instance with values from file or defaults if file
                   doesn't exist or has errors
        """
        if not filepath.exists():
            return cls()
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            return cls(**data)
        except Exception:
            return cls()


# ============================================================
# MAIN REORDERER
# ============================================================


class OdooReorderer:
    """Reorganizes Odoo Python files with single-parse linear workflow.

    This class implements a streamlined approach to reorganizing Odoo Python files:
    - Single parse per file (no caching)
    - Linear workflow: Read → Parse → Reorganize → Write
    - Preserves all code elements while reordering them
    - Supports multiple ordering strategies for fields and methods

    The reorganization follows Odoo conventions:
    - Groups imports by type (stdlib, third-party, Odoo, relative)
    - Orders class attributes by Odoo conventions (_name, _inherit, etc.)
    - Sorts fields by semantic meaning or type
    - Groups methods by category (CRUD, compute, constraints, etc.)
    """

    def __init__(self, config: Config | None = None):
        """Initialize the reorderer with configuration.

        Args:
            config: Configuration instance or None to use defaults
        """
        self.config = config or Config()
        self.ordering = Ordering(self.config)  # Create Ordering instance with config
        self.stats = {
            "files_processed": 0,
            "files_skipped": 0,
            "errors": 0,
        }

    def format_with_black(self, content: str) -> str:
        """Format Python code using isort and Black formatters.

        Applies isort first to organize imports, then Black for code formatting.

        Args:
            content: Python source code to format

        Returns:
            str: Formatted code, or original content if formatting fails
        """
        try:
            mode = black.Mode(
                line_length=self.config.line_length,
                string_normalization=True,
                magic_trailing_comma=self.config.magic_trailing_comma,
                target_versions={black.TargetVersion.PY311},
            )
            return black.format_str(content, mode=mode)
        except Exception as e:
            logger.warning(f"Black formatting failed: {e}")
            return content

    def process_file(self, filepath: Path) -> bool:
        """Process a single Python file through the reorganization workflow.

        Implements a linear, single-parse workflow:
        1. Read file content once
        2. Parse to AST once (no caching)
        3. Reorganize in memory
        4. Optionally format with Black
        5. Write result once (or preview in dry-run mode)

        Creates backup files if configured. Updates statistics for reporting.

        Args:
            filepath: Path to Python file to process

        Returns:
            bool: True if successful, False if errors occurred
        """
        try:
            # Skip non-Python files
            if filepath.suffix not in {".py"}:
                return True

            # Skip backup files
            if filepath.suffix in {".bak", ".pyc", ".pyo"}:
                self.stats["files_skipped"] += 1
                return True

            logger.info(f"Processing {filepath}")

            # Step 1: Read file once
            content = filepath.read_text(encoding="utf-8")

            # Step 2: Parse once (no caching needed)
            tree = ast.parse(content)

            # Step 3: Reorganize in memory (single pass)
            reorganized = self.ordering.reorganize_content(tree)

            # Check if changes needed
            if reorganized == content:
                logger.info(f"No changes needed for {filepath}")
                return True

            # Step 4: Format with Black
            reorganized = self.format_with_black(reorganized)

            # Step 5: Handle dry run or write
            if self.config.dry_run:
                logger.info(f"[DRY RUN] Would update {filepath}")
                return True

            # Create backup if configured
            if self.config.create_backup:
                backup_path = filepath.with_suffix(filepath.suffix + ".bak")
                shutil.copy2(filepath, backup_path)

            # Write file once
            filepath.write_text(reorganized, encoding="utf-8")
            logger.info(f"Successfully reorganized {filepath}")
            self.stats["files_processed"] += 1
            return True

        except Exception as e:
            logger.error(f"Error processing {filepath}: {e}")
            self.stats["errors"] += 1
            return False

    def process_directory(self, directory: Path) -> None:
        """Process all Python files in a directory.

        Finds all .py files (recursively if configured), filters out common
        directories to skip (__pycache__, .git, etc.), and processes each file.
        Prints summary statistics when complete.

        Args:
            directory: Path to directory to process
        """
        pattern = "**/*.py" if self.config.recursive else "*.py"
        files = sorted(directory.glob(pattern))

        # Skip common directories
        skip_dirs = {"__pycache__", ".git", ".venv", "venv", "env"}
        files = [f for f in files if not any(skip in f.parts for skip in skip_dirs)]

        for filepath in files:
            self.process_file(filepath)

        # Summary
        print(f"\nSummary:")
        print(f"  Files processed: {self.stats['files_processed']}")
        print(f"  Files skipped: {self.stats['files_skipped']}")
        print(f"  Errors: {self.stats['errors']}")


# ============================================================
# MAIN ENTRY POINT
# ============================================================


def main():
    """Main entry point for the Odoo reorderer CLI.

    Parses command-line arguments, loads or creates configuration,
    and processes the specified file or directory. Exits with status
    code 0 on success, 1 if errors occurred.
    """
    parser = argparse.ArgumentParser(
        description="Reorganize Odoo Python source files",
    )
    parser.add_argument(
        "path",
        type=Path,
        help="File or directory to process",
    )
    parser.add_argument(
        "--field-strategy",
        choices=["semantic", "type", "strict"],
        default="semantic",
        help="Field ordering strategy",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursive",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview only",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="No backups",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Config file path",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load or create config
    if args.config:
        config = Config.from_file(args.config)
    else:
        config = Config()

    # Override with command-line arguments
    config.field_strategy = args.field_strategy
    config.recursive = args.recursive
    config.dry_run = args.dry_run
    config.create_backup = not args.no_backup

    reorderer = OdooReorderer(config)

    path = args.path
    if path.is_file():
        success = reorderer.process_file(path)
        sys.exit(0 if success else 1)
    elif path.is_dir():
        reorderer.process_directory(path)
        sys.exit(0 if reorderer.stats["errors"] == 0 else 1)
    else:
        print(f"Error: {path} is not a valid file or directory")
        sys.exit(1)


if __name__ == "__main__":
    main()
