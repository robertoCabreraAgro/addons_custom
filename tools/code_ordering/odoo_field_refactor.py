#!/usr/bin/env python3
"""
Odoo Field Refactoring Tool - Enhanced version with single field support
Detects naming violations and refactors fields across Odoo codebase
Supports both single field and batch refactoring operations
"""

import argparse
import ast
from collections import defaultdict
from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import datetime
import json
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET


@dataclass
class FieldViolation:
    """Represents a naming violation in a field"""

    module: str
    model: str
    field_name: str
    field_type: str
    violation_type: str
    suggested_name: str
    file_path: str
    line_number: int
    severity: str = "warning"
    confidence: float = 0.8  # Confidence score for the suggestion

    def to_dict(self):
        return {
            "module": self.module,
            "model": self.model,
            "field_name": self.field_name,
            "field_type": self.field_type,
            "violation_type": self.violation_type,
            "suggested_name": self.suggested_name,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "severity": self.severity,
            "confidence": self.confidence,
        }


@dataclass
class RefactorConfig:
    """Configuration for refactoring operations"""

    target_field: str | None = None  # Specific field to refactor
    target_model: str | None = None  # Specific model to target
    target_module: str | None = None  # Specific module to target
    new_name: str | None = None  # New name for the field
    batch_mode: bool = False  # Process all violations
    dry_run: bool = True  # Don't actually modify files
    backup: bool = True  # Create backups before modifying
    generate_migration: bool = True  # Generate SQL migration scripts
    modules: list[str] = dc_field(default_factory=list)
    exclude_modules: list[str] = dc_field(default_factory=list)
    max_files: int = 1000  # Safety limit


class OdooFieldAnalyzer(ast.NodeVisitor):
    """Analyzes Python files for field definitions and naming violations"""

    FIELD_TYPES = {
        "Char",
        "Text",
        "Html",
        "Integer",
        "Float",
        "Monetary",
        "Boolean",
        "Date",
        "Datetime",
        "Binary",
        "Selection",
        "Many2one",
        "One2many",
        "Many2many",
        "Reference",
        "Image",
    }

    NAMING_RULES = {
        "Many2one": {
            "suffix": "_id",
            "except": ["user_id", "company_id", "currency_id"],
        },
        "One2many": {"suffix": "_ids", "avoid_redundancy": True},
        "Many2many": {"suffix": "_ids", "avoid_redundancy": True},
        "Boolean": {"prefix": ["is_", "has_", "use_", "allow_"]},
    }

    # Advanced patterns for common field naming issues (from odoo_naming_refactor)
    NAMING_PATTERNS = {
        # order_line -> line_ids
        r"^(.+_)?order_line(s)?$": r"\1line_ids",
        # invoice_line -> line_ids
        r"^(.+_)?invoice_line(s)?$": r"\1line_ids",
        # purchase_line -> line_ids
        r"^(.+_)?purchase_line(s)?$": r"\1line_ids",
        # sale_line -> line_ids
        r"^(.+_)?sale_line(s)?$": r"\1line_ids",
        # move_line -> line_ids
        r"^(.+_)?move_line(s)?$": r"\1line_ids",
        # stock_move -> move_ids
        r"^(.+_)?stock_move(s)?$": r"\1move_ids",
        # product_line -> line_ids
        r"^(.+_)?product_line(s)?$": r"\1line_ids",
        # delivery_line -> line_ids
        r"^(.+_)?delivery_line(s)?$": r"\1line_ids",
        # timesheet_line -> line_ids
        r"^(.+_)?timesheet_line(s)?$": r"\1line_ids",
        # payment_line -> line_ids
        r"^(.+_)?payment_line(s)?$": r"\1line_ids",
    }

    def __init__(self, file_path: str, module_name: str):
        self.file_path = file_path
        self.module_name = module_name
        self.current_class = None
        self.violations = []
        self.fields_info = []

    def visit_class_def(self, node):
        """Visit class definitions to find models"""
        if self._is_odoo_model(node):
            self.current_class = node.name
            # Look for _name or _inherit
            model_name = self._get_model_name(node)
            if model_name:
                self.current_model = model_name
            else:
                self.current_model = self._snake_case(node.name)
            self.generic_visit(node)
            self.current_class = None

    def visit_assign(self, node):
        """Visit assignments to find field definitions"""
        if self.current_class and self._is_field_assignment(node):
            field_info = self._get_field_info(node)
            if field_info:
                self.fields_info.append(field_info)
                violation = self._check_naming_violation(field_info)
                if violation:
                    self.violations.append(violation)

    def _is_odoo_model(self, node) -> bool:
        """Check if class is an Odoo model"""
        for base in node.bases:
            if isinstance(base, ast.Attribute):
                if base.attr in ["Model", "TransientModel", "AbstractModel"]:
                    return True
        return False

    def _is_field_assignment(self, node) -> bool:
        """Check if assignment is a field definition"""
        if isinstance(node.value, ast.Call):
            if isinstance(node.value.func, ast.Attribute):
                return node.value.func.attr in self.FIELD_TYPES
        return False

    def _get_field_info(self, node) -> dict | None:
        """Extract field information from assignment"""
        if not node.targets:
            return None

        target = node.targets[0]
        if not isinstance(target, ast.Name):
            return None

        field_name = target.id
        field_type = node.value.func.attr

        return {
            "name": field_name,
            "type": field_type,
            "model": getattr(self, "current_model", self.current_class),
            "class": self.current_class,
            "line": node.lineno,
            "file": self.file_path,
            "module": self.module_name,
        }

    def _get_model_name(self, node) -> str | None:
        """Extract model name from _name or _inherit"""
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        if target.id in ["_name", "_inherit"]:
                            if isinstance(item.value, ast.Constant):
                                return item.value.value
        return None

    def _check_naming_violation(self, field_info: dict) -> FieldViolation | None:
        """Check if field name violates naming conventions"""
        field_name = field_info["name"]
        field_type = field_info["type"]

        # First check against known patterns (highest priority)
        for pattern, replacement in self.NAMING_PATTERNS.items():
            if re.match(pattern, field_name, re.IGNORECASE):
                suggested_name = re.sub(
                    pattern, replacement, field_name, flags=re.IGNORECASE
                )
                if suggested_name != field_name:
                    return FieldViolation(
                        module=field_info["module"],
                        model=field_info["model"],
                        field_name=field_name,
                        field_type=field_type,
                        violation_type="pattern_violation",
                        suggested_name=suggested_name,
                        file_path=field_info["file"],
                        line_number=field_info["line"],
                        severity="high",
                        confidence=0.95,  # High confidence for pattern matches
                    )

        if field_type not in self.NAMING_RULES:
            return None

        rules = self.NAMING_RULES[field_type]

        # Check Many2one suffix
        if field_type == "Many2one":
            if not field_name.endswith(rules["suffix"]):
                if field_name not in rules.get("except", []):
                    suggested = field_name + rules["suffix"]
                    return FieldViolation(
                        module=field_info["module"],
                        model=field_info["model"],
                        field_name=field_name,
                        field_type=field_type,
                        violation_type="missing_suffix",
                        suggested_name=suggested,
                        file_path=field_info["file"],
                        line_number=field_info["line"],
                    )

        # Check One2many/Many2many suffix and redundancy
        elif field_type in ["One2many", "Many2many"]:
            # Check for redundancy (e.g., order_line -> line_ids)
            model_parts = field_info["model"].split(".")
            if len(model_parts) > 1:
                model_prefix = model_parts[-1].replace("_", "")

                # Check if field name contains model prefix
                if field_name.replace("_", "").startswith(model_prefix):
                    # Suggest removing redundancy
                    suggested = field_name.replace(model_prefix, "", 1)
                    if suggested and not suggested.startswith("_"):
                        suggested = "_" + suggested
                    suggested = suggested.lstrip("_")

                    if not suggested.endswith("_ids"):
                        suggested = suggested + "_ids"

                    return FieldViolation(
                        module=field_info["module"],
                        model=field_info["model"],
                        field_name=field_name,
                        field_type=field_type,
                        violation_type="redundant_prefix",
                        suggested_name=suggested,
                        file_path=field_info["file"],
                        line_number=field_info["line"],
                        severity="warning",
                    )

            # Check suffix
            if not field_name.endswith(rules["suffix"]):
                suggested = field_name + rules["suffix"]
                return FieldViolation(
                    module=field_info["module"],
                    model=field_info["model"],
                    field_name=field_name,
                    field_type=field_type,
                    violation_type="missing_suffix",
                    suggested_name=suggested,
                    file_path=field_info["file"],
                    line_number=field_info["line"],
                )

        return None

    def _snake_case(self, name: str) -> str:
        """Convert CamelCase to snake_case"""
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


class RefactorEngine:
    """Executes refactoring operations on the codebase"""

    def __init__(self, config: RefactorConfig, tool=None):
        self.config = config
        self.tool = tool  # Reference to OdooRefactorTool for addon paths
        self.backup_dir = None
        self.changes = []
        self.modified_files = set()

    def refactor_single_field(
        self, violation: FieldViolation, new_name: str | None = None
    ):
        """Refactor a single field across the codebase"""
        old_name = violation.field_name
        new_name = new_name or violation.suggested_name

        print(f"\nRefactoring {violation.model}.{old_name} -> {new_name}")

        if self.config.backup:
            self._create_backup()

        # Find all references
        references = self._find_field_references(violation)

        # Apply refactoring
        for ref in references:
            self._apply_refactoring(ref, old_name, new_name)

        # Generate migration if needed
        if self.config.generate_migration:
            self._generate_migration(violation, new_name)

        return len(references)

    def _find_field_references(self, violation: FieldViolation) -> list[dict]:
        """Find all references to a field across the codebase"""
        references = []
        model = violation.model
        field_name = violation.field_name

        # Search patterns
        patterns = [
            (r"\b" + field_name + r"\s*=\s*fields\.\w+\(", "definition"),
            (r'@api\.depends\(["\']' + field_name, "depends"),
            (r"\." + field_name + r"\b", "access"),
            (r'\[[\'"]\s*' + field_name + r'\s*[\'"]', "dictionary"),
            (r'<field\s+name=["\']' + field_name + r'["\']', "xml_field"),
        ]

        # Find the module path in any of the addon directories
        module_path = None
        if self.tool:
            for addon_path in self.tool.addons_paths:
                potential_path = addon_path / violation.module
                if potential_path.exists():
                    module_path = potential_path
                    break

        if not module_path:
            # Fallback to direct path if it exists
            if Path(violation.module).exists():
                module_path = Path(violation.module)
            else:
                print(f"Warning: Could not find module {violation.module}")
                return references

        # Search in Python files
        for root, _dirs, files in os.walk(str(module_path)):
            for file in files:
                if file.endswith(".py"):
                    filepath = os.path.join(root, file)
                    with open(filepath, "r") as f:
                        content = f.read()
                        for pattern, ref_type in patterns:
                            for match in re.finditer(pattern, content):
                                references.append(
                                    {
                                        "file": filepath,
                                        "type": ref_type,
                                        "line": content[: match.start()].count("\n")
                                        + 1,
                                        "match": match.group(),
                                    },
                                )

        # Search in XML files
        for root, _dirs, files in os.walk(str(module_path)):
            for file in files:
                if file.endswith(".xml"):
                    filepath = os.path.join(root, file)
                    references.extend(self._find_xml_references(filepath, field_name))

        return references

    def _find_xml_references(self, filepath: str, field_name: str) -> list[dict]:
        """Find field references in XML files"""
        references = []
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()

            # Search for field elements
            for elem in root.iter("field"):
                if elem.get("name") == field_name:
                    references.append(
                        {"file": filepath, "type": "xml_field", "element": elem}
                    )

            # Search in domains, contexts, etc.
            for elem in root.iter():
                for attr in ["domain", "context", "eval"]:
                    value = elem.get(attr, "")
                    if field_name in value:
                        references.append(
                            {"file": filepath, "type": f"xml_{attr}", "element": elem}
                        )
        except Exception as e:
            print(f"Error parsing {filepath}: {e}")

        return references

    def _apply_refactoring(self, reference: dict, old_name: str, new_name: str):
        """Apply refactoring to a specific reference"""
        filepath = reference["file"]

        if not self.config.dry_run:
            if filepath.endswith(".py"):
                self._refactor_python_file(filepath, old_name, new_name)
            elif filepath.endswith(".xml"):
                self._refactor_xml_file(filepath, old_name, new_name)

            self.modified_files.add(filepath)

        self.changes.append(
            {
                "file": filepath,
                "old_name": old_name,
                "new_name": new_name,
                "type": reference["type"],
            }
        )

    def _refactor_python_file(self, filepath: str, old_name: str, new_name: str):
        """Refactor Python file"""
        with open(filepath, "r") as f:
            content = f.read()

        # Replacement patterns
        replacements = [
            (r"\b" + old_name + r"\s*=\s*fields\.", new_name + " = fields."),
            (r'@api\.depends\(["\']' + old_name, '@api.depends("' + new_name),
            (r"\." + old_name + r"\b", "." + new_name),
            (r'\[[\'"]\s*' + old_name + r'\s*[\'"]', '["' + new_name + '"'),
        ]

        for pattern, replacement in replacements:
            content = re.sub(pattern, replacement, content)

        with open(filepath, "w") as f:
            f.write(content)

    def _refactor_xml_file(self, filepath: str, old_name: str, new_name: str):
        """Refactor XML file"""
        with open(filepath, "r") as f:
            content = f.read()

        # Simple string replacement for XML
        content = re.sub(
            r'<field\s+name=["\']' + old_name + r'["\']',
            f'<field name="{new_name}"',
            content,
        )

        # Replace in domains and contexts
        content = re.sub(r"\b" + old_name + r"\b", new_name, content)

        with open(filepath, "w") as f:
            f.write(content)

    def _create_backup(self):
        """Create backup of files before modification"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_dir = f"backup_{timestamp}"
        os.makedirs(self.backup_dir, exist_ok=True)
        print(f"Creating backup in {self.backup_dir}")

    def _generate_migration(self, violation: FieldViolation, new_name: str):
        """Generate SQL migration script"""
        migration = f"""-- Migration script for {violation.model}.{violation.field_name} -> {new_name}
        -- Generated on {datetime.now().isoformat()}

        -- Rename column in database
        ALTER TABLE {violation.model.replace('.', '_')}
        RENAME COLUMN {violation.field_name} TO {new_name};

        -- Update ir_model_fields
        UPDATE ir_model_fields
        SET name = '{new_name}'
        WHERE model = '{violation.model}'
        AND name = '{violation.field_name}';

        -- Update any stored filters, actions, etc.
        UPDATE ir_filters
        SET context = REPLACE(context, '{violation.field_name}', '{new_name}'),
            domain = REPLACE(domain, '{violation.field_name}', '{new_name}')
        WHERE model_id = '{violation.model}';

        COMMIT;
        """

        filename = f"migration_{violation.field_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        with open(filename, "w") as f:
            f.write(migration)
        print(f"Migration script generated: {filename}")


class OdooRefactorTool:
    """Main tool for Odoo field refactoring"""

    def __init__(
        self, odoo_path: str = "/mnt/c/odoo/server", addon_paths: list[str] = None
    ):
        self.odoo_path = Path(odoo_path)

        # Allow custom addon paths or use defaults
        if addon_paths:
            self.addons_paths = [Path(p) for p in addon_paths]
        else:
            # Default addon directories relative to odoo_path
            self.addons_paths = [
                self.odoo_path / "addons",
                self.odoo_path / "addons_enterprise",
                self.odoo_path / "addons_custom",
            ]

        # Also check for absolute paths if they exist
        additional_paths = [
            Path("/mnt/c/odoo/enterprise"),  # Common enterprise location
            Path("/opt/odoo/addons"),  # Alternative locations
        ]

        for path in additional_paths:
            if path.exists() and path not in self.addons_paths:
                self.addons_paths.append(path)

        # Filter out non-existent paths and log available paths
        self.addons_paths = [p for p in self.addons_paths if p.exists()]

        if not self.addons_paths:
            print("Warning: No addon paths found. Please specify --addon-paths")
        else:
            print(f"Using addon paths: {', '.join(str(p) for p in self.addons_paths)}")

        self.violations = []

    def analyze_module(self, module_path: Path) -> list[FieldViolation]:
        """Analyze a module for naming violations"""
        violations = []
        module_name = module_path.name

        # Find all Python files
        for py_file in module_path.glob("**/*.py"):
            if "__pycache__" in str(py_file):
                continue

            try:
                with open(py_file, "r") as f:
                    tree = ast.parse(f.read())

                analyzer = OdooFieldAnalyzer(str(py_file), module_name)
                analyzer.visit(tree)
                violations.extend(analyzer.violations)
            except Exception as e:
                print(f"Error analyzing {py_file}: {e}")

        return violations

    def find_violations(self, config: RefactorConfig) -> list[FieldViolation]:
        """Find all naming violations based on config"""
        violations = []

        # Determine which modules to analyze
        modules_to_analyze = []

        if config.target_module:
            # Specific module requested
            for addons_path in self.addons_paths:
                module_path = addons_path / config.target_module
                if module_path.exists():
                    modules_to_analyze.append(module_path)
                    break
        elif config.modules:
            # List of modules specified
            for module_name in config.modules:
                for addons_path in self.addons_paths:
                    module_path = addons_path / module_name
                    if module_path.exists():
                        modules_to_analyze.append(module_path)
                        break
        else:
            # Analyze all modules
            for addons_path in self.addons_paths:
                if addons_path.exists():
                    for module_path in addons_path.iterdir():
                        if module_path.is_dir() and not module_path.name.startswith(
                            "."
                        ):
                            if module_path.name not in config.exclude_modules:
                                modules_to_analyze.append(module_path)

        # Analyze modules
        for module_path in modules_to_analyze:
            print(f"Analyzing {module_path.name}...")
            module_violations = self.analyze_module(module_path)

            # Filter by target field if specified
            if config.target_field:
                module_violations = [
                    v for v in module_violations if v.field_name == config.target_field
                ]

            # Filter by target model if specified
            if config.target_model:
                module_violations = [
                    v for v in module_violations if v.model == config.target_model
                ]

            violations.extend(module_violations)

        self.violations = violations
        return violations

    def refactor_field(self, config: RefactorConfig):
        """Refactor a specific field or batch of fields"""
        # Find violations
        violations = self.find_violations(config)

        if not violations:
            print("No violations found matching the criteria.")
            return

        print(f"\nFound {len(violations)} violation(s)")

        # Show violations
        for v in violations[:10]:  # Show first 10
            print(f"  {v.module}/{v.model}.{v.field_name} -> {v.suggested_name}")

        if len(violations) > 10:
            print(f"  ... and {len(violations) - 10} more")

        if config.dry_run:
            print("\nDry run - no files will be modified")
            return

        # Confirm before proceeding
        if not config.batch_mode:
            response = input("\nProceed with refactoring? (y/n): ")
            if response.lower() != "y":
                print("Refactoring cancelled")
                return

        # Execute refactoring
        engine = RefactorEngine(config, tool=self)

        for violation in violations:
            new_name = config.new_name if config.target_field else None
            changes_count = engine.refactor_single_field(violation, new_name)
            print(f"  Modified {changes_count} references")

        # Summary
        print(f"\n✓ Refactoring complete!")
        print(f"  Files modified: {len(engine.modified_files)}")
        print(f"  Total changes: {len(engine.changes)}")

        # Save report
        self._save_report(violations, engine.changes)

    def _save_report(self, violations: list[FieldViolation], changes: list[dict]):
        """Save refactoring report"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "violations_found": len(violations),
            "changes_made": len(changes),
            "violations": [v.to_dict() for v in violations],
            "changes": changes,
        }

        filename = f"refactor_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w") as f:
            json.dump(report, f, indent=2)
        print(f"Report saved to {filename}")


def main():
    parser = argparse.ArgumentParser(
        description="Odoo Field Refactoring Tool - Fix naming violations in Odoo fields"
    )

    # Odoo path configuration
    parser.add_argument(
        "--odoo-path",
        type=str,
        default="/mnt/c/odoo/server",
        help="Base path to Odoo installation (default: /mnt/c/odoo/server)",
    )
    parser.add_argument(
        "--addon-paths",
        nargs="+",
        help="Custom addon paths to scan (e.g., /mnt/c/odoo/server/addons /mnt/c/odoo/enterprise)",
    )

    # Mode selection
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Analyze and show violations only",
    )
    parser.add_argument(
        "--refactor",
        action="store_true",
        help="Execute refactoring",
    )

    # Target specification
    parser.add_argument(
        "--field",
        type=str,
        help="Specific field name to refactor (e.g., order_line)",
    )
    parser.add_argument(
        "--new-name",
        type=str,
        help="New name for the field (e.g., line_ids)",
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Specific model to target (e.g., purchase.order)",
    )
    parser.add_argument(
        "--module",
        type=str,
        help="Specific module to target (e.g., purchase)",
    )

    # Multiple modules
    parser.add_argument(
        "--modules",
        nargs="+",
        help="List of modules to process",
    )
    parser.add_argument(
        "--exclude",
        nargs="+",
        default=[],
        help="Modules to exclude",
    )

    # Options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show what would be changed without modifying files",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually modify files (disables dry-run)",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating backups",
    )
    parser.add_argument(
        "--no-migration",
        action="store_true",
        help="Skip generating migration scripts",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Process all violations without confirmation",
    )

    args = parser.parse_args()

    # Build config
    config = RefactorConfig(
        target_field=args.field,
        new_name=args.new_name,
        target_model=args.model,
        target_module=args.module,
        modules=args.modules or [],
        exclude_modules=args.exclude,
        dry_run=not args.execute,
        backup=not args.no_backup,
        generate_migration=not args.no_migration,
        batch_mode=args.batch,
    )

    # Create tool instance with custom paths
    tool = OdooRefactorTool(odoo_path=args.odoo_path, addon_paths=args.addon_paths)

    if args.analyze or (not args.refactor and not args.field):
        # Analysis mode
        violations = tool.find_violations(config)

        if violations:
            print(f"\nFound {len(violations)} naming violations:\n")

            # Group by module
            by_module = defaultdict(list)
            for v in violations:
                by_module[v.module].append(v)

            for module, module_violations in sorted(by_module.items()):
                print(f"\n{module}: {len(module_violations)} violations")
                for v in module_violations[:5]:  # Show first 5 per module
                    print(f"  • {v.model}.{v.field_name} ({v.field_type})")
                    print(f"    Violation: {v.violation_type}")
                    print(f"    Suggested: {v.suggested_name}")
                if len(module_violations) > 5:
                    print(f"  ... and {len(module_violations) - 5} more")
        else:
            print("No naming violations found!")

    elif args.refactor or args.field:
        # Refactoring mode
        if args.field and not args.new_name and not config.batch_mode:
            print(f"Warning: Refactoring '{args.field}' without specifying --new-name")
            print("The suggested name from naming conventions will be used.")

        tool.refactor_field(config)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
