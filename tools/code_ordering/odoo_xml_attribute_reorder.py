#!/usr/bin/env python3
"""
Odoo XML Attribute Reordering Tool

This tool reorders attributes in XML files according to Odoo conventions
and applies pretty printing for better readability.
"""

import argparse
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, List


class OdooXMLReorderer:
    """Reorders XML attributes according to Odoo conventions."""

    def __init__(self, dry_run: bool = False, backup: bool = False):
        self.dry_run = dry_run
        self.backup = backup
        self.modifications_count = 0

        # Define attribute order for different element types
        self.attribute_orders = self._build_attribute_orders()

    def _build_attribute_orders(self) -> Dict[str, List[str]]:
        """Define the preferred attribute order for different XML elements."""
        return {
            # View elements
            'record': ['id', 'model', 'inherit_id', 'priority', 'arch_db'],
            'field': ['name', 'string', 'type', 'widget', 'required', 'readonly',
                     'invisible', 'attrs', 'domain', 'context', 'options',
                     'placeholder', 'password', 'filename', 'help', 'groups',
                     'decoration-bf', 'decoration-it', 'decoration-danger',
                     'decoration-info', 'decoration-muted', 'decoration-primary',
                     'decoration-success', 'decoration-warning', 'optional'],
            'button': ['name', 'string', 'type', 'class', 'icon', 'states',
                      'attrs', 'invisible', 'confirm', 'context', 'help', 'groups'],
            'group': ['name', 'string', 'col', 'colspan', 'invisible', 'attrs', 'groups'],
            'page': ['name', 'string', 'invisible', 'attrs', 'groups'],
            'notebook': ['name', 'invisible', 'attrs', 'groups'],
            'sheet': ['name', 'string', 'invisible', 'attrs'],
            'form': ['string', 'create', 'edit', 'delete', 'duplicate', 'import'],
            'tree': ['string', 'create', 'edit', 'delete', 'duplicate', 'import',
                    'default_order', 'decoration-bf', 'decoration-it', 'decoration-danger',
                    'decoration-info', 'decoration-muted', 'decoration-primary',
                    'decoration-success', 'decoration-warning', 'editable'],
            'kanban': ['string', 'create', 'edit', 'delete', 'default_group_by',
                      'default_order', 'quick_create', 'records_draggable'],
            'search': ['string'],
            'pivot': ['string', 'disable_linking', 'display_quantity'],
            'graph': ['string', 'type', 'stacked', 'disable_linking'],
            'calendar': ['string', 'date_start', 'date_stop', 'date_delay',
                        'all_day', 'mode', 'color', 'quick_create'],

            # Search view elements
            'filter': ['name', 'string', 'domain', 'context', 'groups', 'help',
                      'date', 'default_period', 'invisible'],
            'separator': ['string', 'invisible', 'groups'],
            'searchpanel': ['name', 'string', 'select', 'groups', 'icon', 'color'],

            # Action elements
            'act_window': ['id', 'name', 'res_model', 'view_mode', 'view_id',
                          'view_ids', 'search_view_id', 'domain', 'context',
                          'target', 'limit', 'help', 'groups', 'usage'],

            # Menu elements
            'menuitem': ['id', 'name', 'parent', 'sequence', 'action',
                        'groups', 'web_icon', 'web_icon_data'],

            # Template elements
            'template': ['id', 'name', 'inherit_id', 'priority', 'groups',
                        'optional', 'enabled', 'customize_show'],
            't': ['t-if', 't-elif', 't-else', 't-foreach', 't-as',
                 't-esc', 't-raw', 't-field', 't-options', 't-att',
                 't-attf-class', 't-attf-style', 't-attf-href',
                 't-set', 't-value', 't-call', 't-call-assets'],

            # Data elements
            'data': ['noupdate', 'context'],
            'delete': ['model', 'id', 'search'],

            # Generic attributes for unknown elements (fallback)
            '_default': ['id', 'name', 'string', 'model', 'inherit_id',
                        'priority', 'sequence', 'groups']
        }

    def process_file(self, file_path: Path) -> bool:
        """Process a single XML file."""
        if not file_path.exists() or not file_path.suffix == '.xml':
            print(f"Skipping {file_path}: Not an XML file")
            return False

        try:
            # Parse XML
            parser = ET.XMLParser(encoding='utf-8')
            tree = ET.parse(file_path, parser)
            root = tree.getroot()

            # Store original for comparison
            original = ET.tostring(root, encoding='unicode')

            # Process all elements
            self._reorder_element_attributes(root)

            # Check if anything changed
            reordered = ET.tostring(root, encoding='unicode')
            if original == reordered:
                return False

            # Create backup if requested
            if self.backup and not self.dry_run:
                backup_path = file_path.with_suffix(
                    f'.bak.{datetime.now().strftime("%Y%m%d_%H%M%S")}'
                )
                shutil.copy2(file_path, backup_path)
                print(f"Backup created: {backup_path}")

            # Write changes if not dry run
            if not self.dry_run:
                # Pretty print and write
                self._pretty_print_xml(root)
                tree.write(file_path, encoding='utf-8', xml_declaration=True)
                print(f"✓ Modified {file_path}")
            else:
                print(f"Would modify {file_path}")

            self.modifications_count += 1
            return True

        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            return False

    def _reorder_element_attributes(self, element: ET.Element):
        """Recursively reorder attributes for an element and its children."""
        # Get the appropriate attribute order for this element
        tag = element.tag
        if tag in self.attribute_orders:
            order = self.attribute_orders[tag]
        else:
            order = self.attribute_orders['_default']

        # Reorder attributes
        if element.attrib:
            new_attrib = {}

            # First, add attributes in the defined order
            for attr_name in order:
                if attr_name in element.attrib:
                    new_attrib[attr_name] = element.attrib[attr_name]

            # Then add any remaining attributes not in the order
            for attr_name, attr_value in element.attrib.items():
                if attr_name not in new_attrib:
                    new_attrib[attr_name] = attr_value

            # Clear and reset attributes in new order
            element.attrib.clear()
            element.attrib.update(new_attrib)

        # Process children recursively
        for child in element:
            self._reorder_element_attributes(child)

    def _pretty_print_xml(self, element: ET.Element, level: int = 0):
        """Add proper indentation to XML elements."""
        indent = "    "  # 4 spaces
        i = "\n" + level * indent

        if len(element):
            if not element.text or not element.text.strip():
                element.text = i + indent
            if not element.tail or not element.tail.strip():
                element.tail = i
            for child in element:
                self._pretty_print_xml(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = i
        else:
            if level and (not element.tail or not element.tail.strip()):
                element.tail = i

    def process_directory(self, directory: Path, recursive: bool = False) -> int:
        """Process all XML files in a directory."""
        pattern = '**/*.xml' if recursive else '*.xml'
        processed = 0

        for xml_file in directory.glob(pattern):
            if '__pycache__' in str(xml_file) or '.bak.' in str(xml_file):
                continue

            if self.process_file(xml_file):
                processed += 1

        return processed


def main():
    parser = argparse.ArgumentParser(
        description='Reorder XML attributes in Odoo files according to conventions'
    )

    parser.add_argument(
        'path',
        type=str,
        help='File or directory to process'
    )

    parser.add_argument(
        '--recursive', '-r',
        action='store_true',
        help='Process directories recursively'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=False,
        help='Preview changes without modifying files'
    )

    parser.add_argument(
        '--backup',
        action='store_true',
        default=False,
        help='Create backup files before modifying'
    )

    args = parser.parse_args()

    # Create reorderer
    reorderer = OdooXMLReorderer(dry_run=args.dry_run, backup=args.backup)

    # Process path
    path = Path(args.path)

    if path.is_file():
        if reorderer.process_file(path):
            print(f"\n1 file {'would be' if args.dry_run else 'was'} modified")
        else:
            print("No changes needed")
    elif path.is_dir():
        count = reorderer.process_directory(path, recursive=args.recursive)
        if count > 0:
            print(f"\n{count} files {'would be' if args.dry_run else 'were'} modified")
        else:
            print("No changes needed in any files")
    else:
        print(f"Error: {path} not found")
        return 1

    if args.dry_run and reorderer.modifications_count > 0:
        print("\n[DRY RUN] No files were modified. Remove --dry-run to apply changes.")

    return 0


if __name__ == "__main__":
    exit(main())