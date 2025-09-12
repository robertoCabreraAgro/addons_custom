#!/usr/bin/env python3
"""
Validation Tool for Odoo Code Reordering

This tool validates that the reordering process preserves all code elements.

Author: Agromarin Tools
Version: 1.0.0
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Import shared components
from core import (
    BaseASTProcessor,
    ElementExtractor,
    ElementType,
    FileOperations,
    UnifiedElement,
)
from config import ConfigManager, ValidationConfig

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class ReorderValidator:
    """
    Validates that reordering preserves all code elements.

    Now uses shared components for improved efficiency and maintainability.
    """

    def __init__(
        self,
        original_file: Path,
        reordered_file: Path,
        config: Optional[ValidationConfig] = None,
        order_file: Optional[Path] = None,
    ):
        """
        Initialize validator with files and configuration.

        Args:
            original_file: Path to the original/backup file
            reordered_file: Path to the reordered file
            config: Validation configuration (uses default if None)
            order_file: Optional path to the order JSON file
        """
        self.original_file = original_file
        self.reordered_file = reordered_file
        self.order_file = order_file

        # Use provided config or get default
        self.config = config or ValidationConfig.get_default()

        # File operations handler
        self.file_ops = FileOperations()

        # Validation results
        self.results = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "statistics": {},
            "differences": {},
        }

    def validate(self) -> Dict:
        """
        Perform complete validation.

        Returns:
            Dictionary with validation results
        """
        logger.info(f"Validating: {self.original_file} vs {self.reordered_file}")

        try:
            # Read files using shared file operations
            original_content = self.file_ops.read_file(
                self.original_file, use_cache=self.config.use_cache
            )
            reordered_content = self.file_ops.read_file(
                self.reordered_file, use_cache=self.config.use_cache
            )

            # Create AST processors
            original_processor = BaseASTProcessor(original_content, self.original_file)
            reordered_processor = BaseASTProcessor(
                reordered_content, self.reordered_file
            )

            # Extract elements using unified extractor
            original_extractor = ElementExtractor(original_processor)
            reordered_extractor = ElementExtractor(reordered_processor)

            original_elements = original_extractor.extract_all(include_source=False)
            reordered_elements = reordered_extractor.extract_all(include_source=False)

            # Validate each element type
            for element_type in ElementType:
                if self._should_validate_type(element_type):
                    self._validate_element_type(
                        element_type,
                        original_elements.get(element_type, []),
                        reordered_elements.get(element_type, []),
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

    def _should_validate_type(self, element_type: ElementType) -> bool:
        """Check if an element type should be validated based on configuration."""
        type_map = {
            ElementType.IMPORT: "imports",
            ElementType.IMPORT_FROM: "imports",
            ElementType.CLASS: "classes",
            ElementType.METHOD: "methods",
            ElementType.ASYNC_METHOD: "methods",
            ElementType.FIELD: "fields",
            ElementType.FUNCTION: "functions",
            ElementType.ASYNC_FUNCTION: "functions",
            ElementType.MODULE_VAR: "variables",
            ElementType.PROPERTY: "properties",
            ElementType.DECORATOR: "decorators",
        }

        category = type_map.get(element_type)
        if category:
            return self.config.should_validate_element(category)
        return False

    def _validate_element_type(
        self,
        element_type: ElementType,
        original: List[UnifiedElement],
        reordered: List[UnifiedElement],
    ):
        """Validate elements of a specific type."""
        # Get element names
        original_names = {elem.get_full_name() for elem in original}
        reordered_names = {elem.get_full_name() for elem in reordered}

        # Filter ignored elements
        if self.config.ignore_patterns:
            category = element_type.name.lower()
            original_names = {
                name
                for name in original_names
                if not self.config.should_ignore_element(name, category)
            }
            reordered_names = {
                name
                for name in reordered_names
                if not self.config.should_ignore_element(name, category)
            }

        # Check for missing elements
        missing = original_names - reordered_names
        if missing:
            if self.config.strict_mode or not self.config.allow_removed_elements:
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
            if self.config.strict_mode or not self.config.allow_added_elements:
                self.results["is_valid"] = False
                self.results["errors"].append(
                    f"Added {element_type.name}: {sorted(added)}"
                )
            else:
                self.results["warnings"].append(
                    f"Added {element_type.name}: {sorted(added)}"
                )

        # Check order if required
        if self.config.get_validation_rule("require_same_order"):
            if original_names == reordered_names:
                original_order = [elem.get_full_name() for elem in original]
                reordered_order = [elem.get_full_name() for elem in reordered]

                if original_order != reordered_order:
                    if not self.config.allow_order_changes:
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
        """Analyze compliance with the provided order file."""
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

    def _generate_statistics(self, original_elements: Dict, reordered_elements: Dict):
        """Generate validation statistics."""
        stats = {}

        for element_type in ElementType:
            original_count = len(original_elements.get(element_type, []))
            reordered_count = len(reordered_elements.get(element_type, []))

            if original_count > 0 or reordered_count > 0:
                stats[element_type.name] = {
                    "original": original_count,
                    "reordered": reordered_count,
                    "difference": reordered_count - original_count,
                    "status": "✅" if original_count == reordered_count else "⚠️",
                }

        self.results["statistics"] = stats

    def _log_summary(self):
        """Log validation summary."""
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
        if self.results["warnings"] and self.config.verbose:
            logger.warning("\nWarnings:")
            for warning in self.results["warnings"]:
                logger.warning(f"  - {warning}")

        # Log order changes
        if "order_changes" in self.results["differences"]:
            logger.info("\nOrder changes detected (this is expected for reordering)")


def main():
    """Main entry point."""
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
    config = ValidationConfig.get_default()

    if args.config:
        config = ValidationConfig.from_file(Path(args.config))

    if args.strict:
        config.set_strict_mode()
    elif args.lenient:
        config.set_lenient_mode()

    if args.verbose:
        config.verbose = True
        logger.setLevel(logging.DEBUG)

    # Register config with manager
    ConfigManager.register_config("validation", ValidationConfig)
    ConfigManager.set_config("validation", config)

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
