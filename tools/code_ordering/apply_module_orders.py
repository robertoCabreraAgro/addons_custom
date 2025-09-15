#!/usr/bin/env python3
"""
Apply Module Orders Tool

This script applies exported code organization patterns to Python files
in Odoo modules, using the templates created by export_module_orders.py.

Usage:
    python apply_module_orders.py --order-file orders.json --target-module my_module
    python apply_module_orders.py --order-file orders.json --target-directory /path/to/modules
"""

import argparse
import json
import logging
from pathlib import Path
import sys

from config import OdooConfig, ReorderConfig

# Import components from the main tool
from core import FileOperations
from odoo_reorder import CodeReorganizer


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ModuleOrderApplier:
    """
    Applies ordering patterns to Odoo modules.

    This class takes exported ordering patterns and applies them
    to target modules to ensure consistent code organization.
    """

    def __init__(
        self,
        odoo_config: OdooConfig | None = None,
        reorder_config: ReorderConfig | None = None,
    ):
        """
        Initialize the module order applier.

        Args:
            odoo_config: Odoo configuration (optional)
            reorder_config: Reorder configuration (optional)
        """
        self.odoo_config = odoo_config or OdooConfig.get_default()
        self.reorder_config = reorder_config or ReorderConfig.get_default()
        self.file_ops = FileOperations()
        self.reorganizer = CodeReorganizer(odoo_config, reorder_config)

        # Statistics
        self.stats = {
            "files_processed": 0,
            "files_changed": 0,
            "files_skipped": 0,
            "errors": 0,
        }

    def load_order_template(self, order_file: Path) -> dict:
        """
        Load order template from JSON file.

        Args:
            order_file: Path to the order JSON file

        Returns:
            Dictionary containing order data
        """
        if not order_file.exists():
            raise FileNotFoundError(f"Order file not found: {order_file}")

        with open(order_file, "r") as f:
            data = json.load(f)

        logger.info(f"Loaded order template: {data.get('name', 'Unknown')}")
        logger.info(f"  Odoo version: {data.get('odoo_version', 'Unknown')}")
        logger.info(f"  Files in template: {len(data.get('files', {}))}")

        return data

    def find_matching_template(
        self, target_file: Path, template_files: dict
    ) -> dict | None:
        """
        Find a matching template for a target file.

        Args:
            target_file: File to find template for
            template_files: Dictionary of template files

        Returns:
            Matching template data or None
        """
        # Try exact match first
        for template_path, template_data in template_files.items():
            if target_file.name == Path(template_path).name:
                logger.debug(f"  Found exact match: {template_path}")
                return template_data

        # Try pattern matching (e.g., models/*.py matches any model file)
        target_parts = target_file.parts
        for template_path, template_data in template_files.items():
            template_parts = Path(template_path).parts

            # Match by directory structure
            if len(target_parts) >= 2 and len(template_parts) >= 2:
                if target_parts[-2] == template_parts[-2]:  # Same directory name
                    logger.debug(f"  Found directory match: {template_path}")
                    return template_data

        return None

    def apply_to_file(
        self,
        target_file: Path,
        template_data: dict | None = None,
        dry_run: bool = False,
        backup: bool = True,
    ) -> tuple[bool, bool]:
        """
        Apply ordering to a single file.

        Args:
            target_file: File to reorganize
            template_data: Template data to use (optional)
            dry_run: Whether to perform a dry run
            backup: Whether to create backup

        Returns:
            Tuple of (processed, changed)
        """
        try:
            logger.debug(f"Processing: {target_file}")

            # Use the reorganizer to process the file
            new_content, changed = self.reorganizer.reorganize_file(target_file)

            if changed:
                if not dry_run:
                    if backup:
                        self.file_ops.create_backup(target_file)
                    self.file_ops.write_file(target_file, new_content)
                    logger.info(f"  ✅ Reorganized: {target_file}")
                else:
                    logger.info(f"  Would reorganize: {target_file}")

                self.stats["files_changed"] += 1
            else:
                logger.debug(f"  No changes needed: {target_file}")
                self.stats["files_skipped"] += 1

            self.stats["files_processed"] += 1
            return True, changed

        except Exception as e:
            logger.error(f"  ❌ Error processing {target_file}: {e}")
            self.stats["errors"] += 1
            return False, False

    def apply_to_module(
        self,
        module_path: Path,
        template_files: dict,
        dry_run: bool = False,
        backup: bool = True,
    ) -> None:
        """
        Apply ordering to all Python files in a module.

        Args:
            module_path: Path to the module
            template_files: Template files from order export
            dry_run: Whether to perform a dry run
            backup: Whether to create backups
        """
        logger.info(f"Applying ordering to module: {module_path.name}")

        # Get all Python files in module
        python_files = []
        for pattern in ["*.py", "**/*.py"]:
            files = module_path.glob(pattern)
            python_files.extend(
                [
                    f
                    for f in files
                    if not any(skip in f.parts for skip in self.odoo_config.skip_dirs)
                ]
            )

        # Remove duplicates
        python_files = list(set(python_files))
        python_files.sort()

        for py_file in python_files:
            # Skip empty files
            if py_file.stat().st_size == 0:
                continue

            # Find matching template
            relative_path = py_file.relative_to(module_path.parent)
            template = self.find_matching_template(relative_path, template_files)

            # Apply ordering
            self.apply_to_file(py_file, template, dry_run, backup)

    def apply_to_directory(
        self,
        directory: Path,
        template_files: dict,
        dry_run: bool = False,
        backup: bool = True,
    ) -> None:
        """
        Apply ordering to all modules in a directory.

        Args:
            directory: Directory containing modules
            template_files: Template files from order export
            dry_run: Whether to perform a dry run
            backup: Whether to create backups
        """
        # Find all modules in directory
        modules = []
        for manifest_name in self.odoo_config.manifest_files:
            for manifest_path in directory.glob(f"**/{manifest_name}"):
                module_path = manifest_path.parent
                if module_path not in modules:
                    modules.append(module_path)

        logger.info(f"Found {len(modules)} modules to process")

        for module_path in sorted(modules):
            self.apply_to_module(module_path, template_files, dry_run, backup)

    def print_statistics(self) -> None:
        """Print processing statistics."""
        logger.info("\n" + "=" * 50)
        logger.info("Processing Statistics:")
        logger.info(f"  Files processed: {self.stats['files_processed']}")
        logger.info(f"  Files changed: {self.stats['files_changed']}")
        logger.info(f"  Files skipped: {self.stats['files_skipped']}")
        if self.stats["errors"] > 0:
            logger.warning(f"  Errors: {self.stats['errors']}")


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser."""
    parser = argparse.ArgumentParser(
        description="Apply code organization patterns to Odoo modules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Apply to a specific module
  %(prog)s --order-file orders.json --target-module my_module
  
  # Apply to all modules in a directory
  %(prog)s --order-file orders.json --target-directory /opt/odoo/custom_addons
  
  # Dry run to see what would change
  %(prog)s --order-file orders.json --target-module my_module --dry-run
  
  # Apply without creating backups (use with caution!)
  %(prog)s --order-file orders.json --target-module my_module --no-backup
  
  # Apply with specific line length
  %(prog)s --order-file orders.json --target-module my_module --line-length 120
        """,
    )

    parser.add_argument(
        "--order-file",
        "-f",
        type=Path,
        required=True,
        help="JSON file containing the order template",
    )

    parser.add_argument(
        "--target-module", type=Path, help="Target module to apply ordering to"
    )

    parser.add_argument(
        "--target-directory", type=Path, help="Directory containing modules to process"
    )

    parser.add_argument(
        "--target-file", type=Path, help="Single file to apply ordering to"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    parser.add_argument(
        "--no-backup", action="store_true", help="Do not create backup files"
    )

    parser.add_argument(
        "--line-length",
        "-l",
        type=int,
        default=88,
        help="Line length for Black formatting (default: 88)",
    )

    parser.add_argument(
        "--no-black", action="store_true", help="Disable Black formatting"
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )

    return parser


def main():
    """Main entry point."""
    parser = create_argument_parser()
    args = parser.parse_args()

    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate arguments
    if not any([args.target_module, args.target_directory, args.target_file]):
        parser.error(
            "One of --target-module, --target-directory, or --target-file is required"
        )

    # Configure settings
    reorder_config = ReorderConfig.get_default()
    reorder_config.line_length = args.line_length
    reorder_config.use_black = not args.no_black
    reorder_config.dry_run = args.dry_run
    reorder_config.create_backup = not args.no_backup

    # Create applier
    applier = ModuleOrderApplier(reorder_config=reorder_config)

    try:
        # Load order template
        order_data = applier.load_order_template(args.order_file)
        template_files = order_data.get("files", {})

        # Apply to target
        if args.target_file:
            # Single file
            if not args.target_file.exists():
                logger.error(f"Target file not found: {args.target_file}")
                sys.exit(1)

            template = applier.find_matching_template(args.target_file, template_files)
            applier.apply_to_file(
                args.target_file, template, args.dry_run, not args.no_backup
            )

        elif args.target_module:
            # Single module
            if not args.target_module.exists():
                logger.error(f"Target module not found: {args.target_module}")
                sys.exit(1)

            applier.apply_to_module(
                args.target_module, template_files, args.dry_run, not args.no_backup
            )

        elif args.target_directory:
            # Directory of modules
            if not args.target_directory.exists():
                logger.error(f"Target directory not found: {args.target_directory}")
                sys.exit(1)

            applier.apply_to_directory(
                args.target_directory, template_files, args.dry_run, not args.no_backup
            )

        # Print statistics
        applier.print_statistics()

    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
