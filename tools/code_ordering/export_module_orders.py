#!/usr/bin/env python3
"""
Export Module Orders Tool

This script exports the code organization patterns from Python files
in multiple Odoo modules, creating a comprehensive ordering template
that can be applied to other modules.

Usage:
    python export_module_orders.py [--modules module1,module2] [--output orders.json]
    python export_module_orders.py --scan-directory /path/to/addons
"""

import argparse
import json
import logging
from pathlib import Path
import sys

from config import OdooConfig

# Import components from the main tool
from core import FileOperations
from odoo_reorder import OrderExport, OrderExporter, OrderExportType


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ModuleOrderExporter:
    """
    Exports ordering patterns from multiple Odoo modules.

    This class scans specified modules and exports the code organization
    patterns from all Python files, creating a comprehensive template.
    """

    def __init__(self, odoo_config: OdooConfig | None = None):
        """
        Initialize the module order exporter.

        Args:
            odoo_config: Odoo configuration (optional)
        """
        self.odoo_config = odoo_config or OdooConfig.get_default()
        self.file_ops = FileOperations()
        self.order_exporter = OrderExporter()

        # Statistics
        self.stats = {
            "modules_processed": 0,
            "files_processed": 0,
            "classes_found": 0,
            "methods_found": 0,
            "errors": 0,
        }

    def find_odoo_modules(self, base_path: Path) -> list[Path]:
        """
        Find all Odoo modules in a directory.

        Args:
            base_path: Base directory to search for modules

        Returns:
            List of module paths
        """
        modules = []

        # Look for directories containing manifest files
        for manifest_name in self.odoo_config.manifest_files:
            for manifest_path in base_path.glob(f"**/{manifest_name}"):
                module_path = manifest_path.parent
                if module_path not in modules:
                    modules.append(module_path)
                    logger.debug(f"Found module: {module_path.name}")

        return sorted(modules)

    def get_module_python_files(self, module_path: Path) -> list[Path]:
        """
        Get all Python files in a module, organized by directory.

        Args:
            module_path: Path to the Odoo module

        Returns:
            List of Python file paths
        """
        python_files = []

        # Define the order of directories to scan
        ordered_dirs = ["models", "controllers", "wizards", "report", "tests"]

        # First, get files from ordered directories
        for dir_name in ordered_dirs:
            dir_path = module_path / dir_name
            if dir_path.exists() and dir_path.is_dir():
                files = sorted(dir_path.glob("**/*.py"))
                # Filter out __pycache__ and other unwanted files
                files = [
                    f
                    for f in files
                    if not any(skip in f.parts for skip in self.odoo_config.skip_dirs)
                ]
                python_files.extend(files)

        # Then get Python files in module root (like __init__.py, __manifest__.py)
        root_files = sorted(module_path.glob("*.py"))
        python_files.extend(root_files)

        # Finally, get files from any other directories
        for item in module_path.iterdir():
            if item.is_dir() and item.name not in ordered_dirs:
                if not self.odoo_config.should_skip_directory(item.name):
                    files = sorted(item.glob("**/*.py"))
                    files = [
                        f
                        for f in files
                        if not any(
                            skip in f.parts for skip in self.odoo_config.skip_dirs
                        )
                    ]
                    python_files.extend(files)

        # Remove duplicates while preserving order
        seen = set()
        unique_files = []
        for f in python_files:
            if f not in seen:
                seen.add(f)
                unique_files.append(f)

        return unique_files

    def export_module_orders(
        self, module_paths: list[Path], odoo_version: str = "19.0"
    ) -> OrderExport:
        """
        Export ordering from multiple modules.

        Args:
            module_paths: List of module paths to process
            odoo_version: Odoo version string

        Returns:
            Combined OrderExport data
        """
        combined_export = OrderExport(
            odoo_version=odoo_version,
            export_type=OrderExportType.MODULE,
            name="Multi-module order export",
            files={},
        )

        for module_path in module_paths:
            logger.info(f"Processing module: {module_path.name}")
            self.stats["modules_processed"] += 1

            # Get all Python files in the module
            python_files = self.get_module_python_files(module_path)

            for py_file in python_files:
                try:
                    # Skip empty files
                    if py_file.stat().st_size == 0:
                        continue

                    logger.debug(f"  Processing: {py_file.relative_to(module_path)}")

                    # Export order from this file
                    file_export = self.order_exporter.export_file(py_file, odoo_version)

                    # Add to combined export with relative path as key
                    relative_path = py_file.relative_to(module_path.parent)
                    combined_export.files[str(relative_path)] = file_export.files[
                        str(py_file)
                    ]

                    self.stats["files_processed"] += 1

                    # Update statistics
                    file_order = file_export.files[str(py_file)]
                    self.stats["classes_found"] += len(file_order.classes)
                    for class_order in file_order.classes:
                        for methods in class_order.methods.values():
                            self.stats["methods_found"] += len(methods)

                except Exception as e:
                    logger.error(f"  Error processing {py_file}: {e}")
                    self.stats["errors"] += 1
                    continue

        return combined_export

    def export_from_module_list(
        self,
        module_names: list[str],
        search_paths: list[Path],
        odoo_version: str = "19.0",
    ) -> OrderExport:
        """
        Export ordering from a list of module names.

        Args:
            module_names: List of module names to find and process
            search_paths: Paths to search for modules
            odoo_version: Odoo version string

        Returns:
            Combined OrderExport data
        """
        module_paths = []

        for search_path in search_paths:
            if not search_path.exists():
                logger.warning(f"Search path does not exist: {search_path}")
                continue

            for module_name in module_names:
                module_path = search_path / module_name
                if module_path.exists() and module_path.is_dir():
                    # Verify it's an Odoo module
                    is_module = any(
                        (module_path / manifest).exists()
                        for manifest in self.odoo_config.manifest_files
                    )
                    if is_module:
                        module_paths.append(module_path)
                        logger.info(f"Found module: {module_name} at {module_path}")
                    else:
                        logger.warning(
                            f"{module_path} exists but is not an Odoo module"
                        )

        if not module_paths:
            logger.error("No valid modules found")
            return OrderExport()

        return self.export_module_orders(module_paths, odoo_version)

    def save_export(
        self, export_data: OrderExport, output_path: Path, pretty: bool = True
    ) -> None:
        """
        Save the export data to a JSON file.

        Args:
            export_data: OrderExport data to save
            output_path: Path for output file
            pretty: Whether to pretty-print the JSON
        """
        # Convert to dictionary
        data = {
            "version": export_data.version,
            "odoo_version": export_data.odoo_version,
            "export_date": export_data.export_date,
            "type": export_data.export_type.name.lower(),
            "name": export_data.name,
            "statistics": self.stats,
            "files": {},
        }

        # Add file orders
        for file_path, file_order in export_data.files.items():
            data["files"][file_path] = {
                "filepath": file_order.filepath,
                "import_groups": file_order.import_groups,
                "import_statements": file_order.import_statements,
                "classes": [
                    {
                        "name": cls.name,
                        "model_attributes": cls.model_attributes,
                        "fields": cls.fields,
                        "sql_constraints": cls.sql_constraints,
                        "model_indexes": cls.model_indexes,
                        "methods": cls.methods,
                        "section_headers": cls.section_headers,
                    }
                    for cls in file_order.classes
                ],
                "functions": file_order.functions,
                "module_level_vars": file_order.module_level_vars,
            }

        # Save to file
        with open(output_path, "w") as f:
            if pretty:
                json.dump(data, f, indent=2, sort_keys=True)
            else:
                json.dump(data, f)

        logger.info(f"✅ Order export saved to: {output_path}")
        logger.info(f"   Modules processed: {self.stats['modules_processed']}")
        logger.info(f"   Files processed: {self.stats['files_processed']}")
        logger.info(f"   Classes found: {self.stats['classes_found']}")
        logger.info(f"   Methods found: {self.stats['methods_found']}")
        if self.stats["errors"] > 0:
            logger.warning(f"   Errors encountered: {self.stats['errors']}")


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser."""
    parser = argparse.ArgumentParser(
        description="Export code organization patterns from Odoo modules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export from specific modules in current directory
  %(prog)s --modules sale,purchase,stock
  
  # Export from modules in a specific directory
  %(prog)s --modules sale,purchase --search-path /opt/odoo/addons
  
  # Scan and export all modules in a directory
  %(prog)s --scan-directory /opt/odoo/addons
  
  # Export with custom output file
  %(prog)s --modules sale --output sale_order_template.json
  
  # Export for specific Odoo version
  %(prog)s --modules sale --odoo-version 17.0
        """,
    )

    parser.add_argument(
        "--modules", type=str, help="Comma-separated list of module names to export"
    )

    parser.add_argument(
        "--scan-directory",
        type=Path,
        help="Scan directory for all Odoo modules and export their ordering",
    )

    parser.add_argument(
        "--search-paths",
        type=str,
        default=".,../",
        help="Comma-separated paths to search for modules (default: current and parent dir)",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default="module_orders.json",
        help="Output file for the export (default: module_orders.json)",
    )

    parser.add_argument(
        "--odoo-version",
        default="19.0",
        choices=["17.0", "18.0", "19.0"],
        help="Odoo version (default: 19.0)",
    )

    parser.add_argument(
        "--include-tests", action="store_true", help="Include test files in the export"
    )

    parser.add_argument(
        "--compact",
        action="store_true",
        help="Save JSON in compact format (no pretty-printing)",
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

    # Configure Odoo settings
    odoo_config = OdooConfig.get_default()
    odoo_config.version = args.odoo_version

    if not args.include_tests:
        if "tests" not in odoo_config.skip_dirs:
            odoo_config.skip_dirs.append("tests")

    # Create exporter
    exporter = ModuleOrderExporter(odoo_config)

    try:
        # Determine what to export
        if args.scan_directory:
            # Scan directory for all modules
            if not args.scan_directory.exists():
                logger.error(f"Directory does not exist: {args.scan_directory}")
                sys.exit(1)

            logger.info(f"Scanning for modules in: {args.scan_directory}")
            module_paths = exporter.find_odoo_modules(args.scan_directory)

            if not module_paths:
                logger.error("No Odoo modules found in directory")
                sys.exit(1)

            logger.info(f"Found {len(module_paths)} modules")
            export_data = exporter.export_module_orders(module_paths, args.odoo_version)

        elif args.modules:
            # Export specific modules
            module_names = [m.strip() for m in args.modules.split(",")]
            search_paths = [Path(p.strip()) for p in args.search_paths.split(",")]

            logger.info(f"Looking for modules: {', '.join(module_names)}")
            export_data = exporter.export_from_module_list(
                module_names, search_paths, args.odoo_version
            )

        else:
            # Default: scan current directory
            current_dir = Path.cwd()

            # Check if current directory is a module
            is_module = any(
                (current_dir / manifest).exists()
                for manifest in odoo_config.manifest_files
            )

            if is_module:
                logger.info(f"Exporting from current module: {current_dir.name}")
                export_data = exporter.export_module_orders(
                    [current_dir], args.odoo_version
                )
            else:
                # Look for modules in current directory
                logger.info("Scanning current directory for modules...")
                module_paths = exporter.find_odoo_modules(current_dir)

                if not module_paths:
                    logger.error(
                        "No Odoo modules found. Use --modules or --scan-directory"
                    )
                    parser.print_help()
                    sys.exit(1)

                logger.info(f"Found {len(module_paths)} modules")
                export_data = exporter.export_module_orders(
                    module_paths, args.odoo_version
                )

        # Save the export
        exporter.save_export(export_data, args.output, pretty=not args.compact)

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
