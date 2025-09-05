#!/usr/bin/env python3
# Copyright 2025 AgroMarin
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""
Test runner script for base_geoengine module tests.

This script can be used to run all geoengine tests and provides detailed
output about test results and any ORM compatibility issues.

Usage:
    python test_runner.py [--verbose] [--test-module TEST_MODULE]

Example:
    python test_runner.py --verbose
    python test_runner.py --test-module test_geo_fields
"""

import os
import sys
import argparse
import subprocess
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class GeoEngineTestRunner:
    """Test runner for base_geoengine tests."""

    def __init__(self, odoo_bin_path=None, db_name=None, verbose=False):
        self.odoo_bin_path = odoo_bin_path or self._find_odoo_bin()
        self.db_name = db_name or "test_geoengine"
        self.verbose = verbose
        self.test_modules = [
            "test_geo_fields",
            "test_geo_operators",
            "test_orm_compatibility",
            "test_spatial_queries",
        ]

    def _find_odoo_bin(self):
        """Try to find odoo-bin executable."""
        possible_paths = [
            "/mnt/c/odoo/server/odoo-bin",
            "./odoo-bin",
            "../odoo-bin",
            "../../odoo-bin",
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        logger.warning("Could not find odoo-bin, using default path")
        return "odoo-bin"

    def run_test_module(self, test_module):
        """Run a specific test module."""
        cmd = [
            self.odoo_bin_path,
            "--test-enable",
            "--test-tags",
            f"base_geoengine.{test_module}",
            "--database",
            self.db_name,
            "--addons-path",
            "/mnt/c/odoo/server/addons_custom",
            "--init",
            "base_geoengine",
            "--stop-after-init",
        ]

        if self.verbose:
            cmd.extend(["--log-level", "debug"])

        logger.info(f"Running test module: {test_module}")
        logger.debug(f"Command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300  # 5 minute timeout
            )

            return {
                "module": test_module,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

        except subprocess.TimeoutExpired:
            logger.error(f"Test module {test_module} timed out")
            return {
                "module": test_module,
                "returncode": -1,
                "stdout": "",
                "stderr": "Test timed out after 5 minutes",
            }
        except Exception as e:
            logger.error(f"Error running test module {test_module}: {e}")
            return {
                "module": test_module,
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
            }

    def run_all_tests(self, specific_module=None):
        """Run all test modules or a specific one."""
        modules_to_run = [specific_module] if specific_module else self.test_modules
        results = []

        logger.info("Starting base_geoengine test suite")
        logger.info(f"Testing modules: {', '.join(modules_to_run)}")

        for module in modules_to_run:
            result = self.run_test_module(module)
            results.append(result)

            if result["returncode"] == 0:
                logger.info(f"✅ {module} - PASSED")
            else:
                logger.error(f"❌ {module} - FAILED")
                if self.verbose:
                    logger.error(f"STDERR: {result['stderr']}")

        return results

    def analyze_results(self, results):
        """Analyze test results and provide summary."""
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r["returncode"] == 0)
        failed_tests = total_tests - passed_tests

        logger.info("=" * 60)
        logger.info("TEST RESULTS SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total test modules: {total_tests}")
        logger.info(f"Passed: {passed_tests}")
        logger.info(f"Failed: {failed_tests}")

        if failed_tests > 0:
            logger.error("\nFAILED MODULES:")
            for result in results:
                if result["returncode"] != 0:
                    logger.error(f"- {result['module']}")
                    if result["stderr"]:
                        logger.error(f"  Error: {result['stderr'][:200]}...")

        # Check for ORM compatibility issues
        self._check_orm_compatibility_issues(results)

        # Check for PostGIS issues
        self._check_postgis_issues(results)

        return failed_tests == 0

    def _check_orm_compatibility_issues(self, results):
        """Check for potential ORM compatibility issues in test output."""
        orm_indicators = [
            "AttributeError",
            "MethodError",
            "signature mismatch",
            "domain",
            "search",
            "fields_get",
        ]

        logger.info("\n" + "=" * 40)
        logger.info("ORM COMPATIBILITY CHECK")
        logger.info("=" * 40)

        compatibility_issues = []
        for result in results:
            full_output = result["stdout"] + result["stderr"]
            for indicator in orm_indicators:
                if indicator.lower() in full_output.lower():
                    compatibility_issues.append((result["module"], indicator))

        if compatibility_issues:
            logger.warning("Potential ORM compatibility issues detected:")
            for module, issue in compatibility_issues:
                logger.warning(f"- {module}: {issue}")
        else:
            logger.info("✅ No ORM compatibility issues detected")

    def _check_postgis_issues(self, results):
        """Check for PostGIS-related issues."""
        postgis_indicators = ["PostGIS", "ST_", "geometry", "spatial", "GIST"]

        logger.info("\n" + "=" * 40)
        logger.info("POSTGIS COMPATIBILITY CHECK")
        logger.info("=" * 40)

        postgis_issues = []
        for result in results:
            full_output = result["stdout"] + result["stderr"]
            for indicator in postgis_indicators:
                if (
                    "error" in full_output.lower()
                    and indicator.lower() in full_output.lower()
                ):
                    postgis_issues.append((result["module"], indicator))

        if postgis_issues:
            logger.warning("Potential PostGIS issues detected:")
            for module, issue in postgis_issues:
                logger.warning(f"- {module}: {issue}")
        else:
            logger.info("✅ No PostGIS compatibility issues detected")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run base_geoengine tests")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )
    parser.add_argument("--test-module", "-t", help="Run specific test module only")
    parser.add_argument("--odoo-bin", help="Path to odoo-bin executable")
    parser.add_argument(
        "--database", "-d", default="test_geoengine", help="Test database name"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    runner = GeoEngineTestRunner(
        odoo_bin_path=args.odoo_bin, db_name=args.database, verbose=args.verbose
    )

    try:
        results = runner.run_all_tests(args.test_module)
        success = runner.analyze_results(results)

        if success:
            logger.info("🎉 All tests passed!")
            sys.exit(0)
        else:
            logger.error("💥 Some tests failed!")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Test run interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
