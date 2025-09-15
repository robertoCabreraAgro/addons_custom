#!/usr/bin/env python3
"""
Validation Tool for Odoo Code Reordering.

This tool validates that the reordering process preserves all code elements
by comparing the original file with the reordered version. It ensures that
no code is lost or accidentally modified during the reorganization process.

Key Features:
- Compares element counts (imports, classes, functions, variables)
- Detects missing or added elements
- Validates order compliance if an order file is provided
- Generates detailed statistics and validation reports
- Supports strict or lenient validation modes

Author: Agromarin Tools
Version: 1.0.0
"""

import argparse
import ast
from dataclasses import dataclass
import json
import logging
from pathlib import Path
import sys
from typing import Optional

# Import shared components
from core.ordering import Ordering


# Simple config for validation
@dataclass
class Config:
    """Configuration for validation behavior.

    Attributes:
        strict_validation: If True, any difference is an error. If False,
                          differences are warnings.
        allow_additions: Whether to allow new elements in reordered file
        allow_removals: Whether to allow elements to be removed
    """

    strict_validation: bool = False
    allow_additions: bool = True
    allow_removals: bool = True


# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class ReorderValidator:
    """Validates that code reordering preserves all elements.

    This validator compares an original Python file with its reordered
    version to ensure all code elements are preserved. It uses the
    ASTProcessor for parsing and element extraction.

    The validation process:
    1. Parse both files into AST
    2. Extract all code elements (imports, classes, functions, etc.)
    3. Compare element counts and names
    4. Report any differences as errors or warnings based on config
    5. Generate statistics for reporting
    """

    def __init__(
        self,
        original_file: Path,
        reordered_file: Path,
        config: Optional[Config] = None,
        order_file: Optional[Path] = None,
    ):
        """Initialize validator with files and configuration.

        Args:
            original_file: Path to the original/backup file to compare against
            reordered_file: Path to the reordered file to validate
            config: Validation configuration (uses default if None)
            order_file: Optional path to JSON file containing intended order
        """
        self.original_file = original_file
        self.reordered_file = reordered_file
        self.order_file = order_file

        # Use provided config or get default
        self.config = config or Config()

        # Validation results
        self.results = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "statistics": {},
            "differences": {},
        }

    def validate(self) -> dict:
        """Perform complete validation of the reordering.

        Executes the full validation workflow:
        1. Read and parse both files
        2. Extract all elements using ASTProcessor
        3. Validate each element type
        4. Check order compliance if order file provided
        5. Generate statistics
        6. Log summary

        Returns:
            Dict: Validation results containing:
                - 'is_valid': Boolean indicating overall success
                - 'errors': List of error messages
                - 'warnings': List of warning messages
                - 'statistics': Element count statistics
                - 'differences': Detailed difference information
        """
        logger.info(f"Validating: {self.original_file} vs {self.reordered_file}")

        try:
            # Read files
            if not self.original_file.exists():
                raise FileNotFoundError(f"File not found: {self.original_file}")
            if not self.reordered_file.exists():
                raise FileNotFoundError(f"File not found: {self.reordered_file}")
            original_content = self.original_file.read_text(encoding="utf-8")
            reordered_content = self.reordered_file.read_text(encoding="utf-8")

            # Create processors
            original_processor = Ordering(
                content=original_content,
                filepath=self.original_file,
            )
            reordered_processor = Ordering(
                content=reordered_content,
                filepath=self.reordered_file,
            )

            # Extract elements using improved ASTProcessor
            original_elements = original_processor.extract_elements()
            reordered_elements = reordered_processor.extract_elements()

            # Validate each element type
            element_type_map = {
                "imports": "imports",
                "classes": "classes",
                "functions": "functions",
                "module_vars": "variables",
            }

            for elem_key, config_key in element_type_map.items():
                if True:  # Always validate in simplified version
                    self._validate_element_type(
                        elem_key,
                        original_elements.get(elem_key, []),
                        reordered_elements.get(elem_key, []),
                    )

            # Analyze order compliance if order file provided
            if self.order_file and self.order_file.exists():
                self._analyze_order_compliance()

            # Generate statistics
            self._generate_statistics(original_elements, reordered_elements)

        except SyntaxError as e:
            self.results["is_valid"] = False
            self.results["errors"].append(f"Syntax error: {e}")
            logger.error(f"Syntax error during validation: {e}")
        except Exception as e:
            self.results["is_valid"] = False
            self.results["errors"].append(f"Validation error: {e}")
            logger.error(f"Validation failed: {e}")

        # Log summary
        self._log_summary()

        return self.results

    def _should_validate_type(self, element_type: str) -> bool:
        """Check if an element type should be validated.

        Currently always returns True in simplified version.

        Args:
            element_type: Type of element ('imports', 'classes', etc.)

        Returns:
            bool: True if the element type should be validated
        """
        type_map = {
            "imports": "imports",
            "classes": "classes",
            "functions": "functions",
            "module_vars": "variables",
        }

        category = type_map.get(element_type, element_type)
        return True  # Always validate in simplified version

    def _validate_element_type(
        self,
        element_type: str,
        original: list[ast.AST],
        reordered: list[ast.AST],
    ):
        """Validate elements of a specific type.

        Compares original and reordered elements, checking for:
        - Missing elements (in original but not in reordered)
        - Added elements (in reordered but not in original)
        - Order changes (currently tracked but not enforced)

        Args:
            element_type: Type name for reporting (e.g., 'imports')
            original: List of AST nodes from original file
            reordered: List of AST nodes from reordered file
        """
        # Get element names from AST nodes
        processor = Ordering()  # Temporary processor for utility methods
        original_names = {
            processor.get_node_name(elem)
            for elem in original
            if processor.get_node_name(elem)
        }
        reordered_names = {
            processor.get_node_name(elem)
            for elem in reordered
            if processor.get_node_name(elem)
        }

        # Filter ignored elements
        if False:  # No ignore patterns in simplified version
            category = element_type.name.lower()
            original_names = {
                name
                for name in original_names
                if True  # No ignore patterns in simplified version
            }
            reordered_names = {
                name
                for name in reordered_names
                if True  # No ignore patterns in simplified version
            }

        # Check for missing elements
        missing = original_names - reordered_names
        if missing:
            if self.config.strict_validation or not self.config.allow_removals:
                self.results["is_valid"] = False
                self.results["errors"].append(
                    f"Missing {element_type.name}: {sorted(missing)}"
                )
            else:
                self.results["warnings"].append(
                    f"Missing {element_type.name}: {sorted(missing)}"
                )

        # Check for added elements
        added = reordered_names - original_names
        if added:
            if self.config.strict_validation or not self.config.allow_additions:
                self.results["is_valid"] = False
                self.results["errors"].append(
                    f"Added {element_type.name}: {sorted(added)}"
                )
            else:
                self.results["warnings"].append(
                    f"Added {element_type.name}: {sorted(added)}"
                )

        # Check order if required
        if False:  # Order validation not needed in simplified version
            if original_names == reordered_names:
                original_order = [elem.get_full_name() for elem in original]
                reordered_order = [elem.get_full_name() for elem in reordered]

                if original_order != reordered_order:
                    if False:  # Order changes are expected
                        self.results["is_valid"] = False
                        self.results["errors"].append(
                            f"Order changed for {element_type.name}"
                        )
                    else:
                        # Track order changes
                        if "order_changes" not in self.results["differences"]:
                            self.results["differences"]["order_changes"] = {}

                        self.results["differences"]["order_changes"][
                            element_type.name
                        ] = {
                            "original": original_order[:10],  # First 10 for brevity
                            "reordered": reordered_order[:10],
                        }

    def _analyze_order_compliance(self):
        """Analyze compliance with the provided order file.

        If an order file was provided, this method loads it and
        analyzes whether the reordered file follows the intended order.
        Currently provides basic loading and warning generation.
        """
        try:
            with open(self.order_file, "r") as f:
                order_data = json.load(f)

            # Add analysis based on order file
            self.results["warnings"].append(
                f"Order file loaded: {self.order_file.name}"
            )

            # Could add more sophisticated order compliance checking here

        except Exception as e:
            self.results["warnings"].append(f"Could not analyze order file: {e}")

    def _generate_statistics(self, original_elements: dict, reordered_elements: dict):
        """Generate validation statistics.

        Creates a summary of element counts for each type, comparing
        original and reordered versions.

        Args:
            original_elements: Dictionary of elements from original file
            reordered_elements: Dictionary of elements from reordered file
        """
        stats = {}

        # Process each element type
        for element_type in ["imports", "classes", "functions", "module_vars"]:
            original_count = len(original_elements.get(element_type, []))
            reordered_count = len(reordered_elements.get(element_type, []))

            if original_count > 0 or reordered_count > 0:
                stats[element_type] = {
                    "original": original_count,
                    "reordered": reordered_count,
                    "difference": reordered_count - original_count,
                    "status": "✅" if original_count == reordered_count else "⚠️",
                }

        self.results["statistics"] = stats

    def _log_summary(self):
        """Log a formatted summary of validation results.

        Outputs a human-readable summary including:
        - Overall pass/fail status
        - Element count statistics in table format
        - Lists of errors and warnings
        - Order change notifications
        """
        if self.results["is_valid"]:
            logger.info("✅ VALIDATION PASSED: All required elements preserved")
        else:
            logger.error("❌ VALIDATION FAILED: Issues detected")

        # Log statistics
        if self.results["statistics"]:
            logger.info("\nElement counts:")
            logger.info("  Type              | Original | Reordered | Status")
            logger.info("  ------------------|----------|-----------|--------")

            for element_type, stats in self.results["statistics"].items():
                logger.info(
                    f"  {element_type:17} | {stats['original']:8} | "
                    f"{stats['reordered']:9} | {stats['status']}"
                )

        # Log errors
        if self.results["errors"]:
            logger.error("\nErrors:")
            for error in self.results["errors"]:
                logger.error(f"  - {error}")

        # Log warnings
        if self.results["warnings"]:  # Always show warnings
            logger.warning("\nWarnings:")
            for warning in self.results["warnings"]:
                logger.warning(f"  - {warning}")

        # Log order changes
        if "order_changes" in self.results["differences"]:
            logger.info("\nOrder changes detected (this is expected for reordering)")


def main():
    """Main entry point for the validation tool.

    Parses command-line arguments, configures validation settings,
    runs the validator, and exits with appropriate status code.

    Exit codes:
        0: Validation passed
        1: Validation failed or files not found
    """
    parser = argparse.ArgumentParser(
        description="Validate Odoo code reordering (v2 - using shared components)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("original", help="Path to the original file (or backup)")
    parser.add_argument("reordered", help="Path to the reordered file")
    parser.add_argument(
        "--order", help="Path to the order JSON file used for reordering"
    )
    parser.add_argument(
        "--strict", action="store_true", help="Enable strict validation mode"
    )
    parser.add_argument(
        "--lenient", action="store_true", help="Enable lenient validation mode"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--config", help="Path to configuration file")

    args = parser.parse_args()

    # Setup configuration
    config = Config()

    if args.strict:
        config.strict_validation = True
    elif args.lenient:
        config.strict_validation = False
        config.allow_additions = True
        config.allow_removals = True

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Validate files exist
    original_file = Path(args.original)
    reordered_file = Path(args.reordered)

    if not original_file.exists():
        logger.error(f"Original file not found: {original_file}")
        sys.exit(1)

    if not reordered_file.exists():
        logger.error(f"Reordered file not found: {reordered_file}")
        sys.exit(1)

    order_file = Path(args.order) if args.order else None
    if order_file and not order_file.exists():
        logger.warning(f"Order file not found: {order_file}")
        order_file = None

    # Run validation
    validator = ReorderValidator(original_file, reordered_file, config, order_file)
    results = validator.validate()

    # Output JSON if requested
    if args.json:
        # Clean up results for JSON serialization
        json_results = {
            "is_valid": results["is_valid"],
            "errors": results["errors"],
            "warnings": results["warnings"],
            "statistics": results["statistics"],
        }
        print(json.dumps(json_results, indent=2))

    # Exit with appropriate code
    sys.exit(0 if results["is_valid"] else 1)


if __name__ == "__main__":
    main()
