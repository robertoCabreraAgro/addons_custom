#!/usr/bin/env python3
"""
Centralized Pattern Definitions

This module consolidates all pattern definitions used across the code ordering system
to eliminate redundancy and ensure consistency.

Author: Agromarin Tools
Version: 1.0.0
"""

from typing import Dict, List, Set


class OdooPatterns:
    """Centralized Odoo-specific patterns."""

    # Model attribute patterns
    MODEL_ATTRIBUTES: Set[str] = {
        "_name",
        "_inherits",
        "_inherit",
        "_description",
        "_table",
        "_table_query",
        "_sequence",
        "_active_name",
        "_date_name",
        "_fold_name",
        "_parent_name",
        "_parent_store",
        "_parent_order",
        "_rec_name",
        "_rec_names_search",
        "_auto",
        "_abstract",
        "_check_company_auto",
        "_custom",
        "_depends",
        "_register",
        "_transient",
        "_transient_max_count",
        "_transient_max_hours",
        "_module",
        "_translate",
        "_allow_sudo_commands",
        "_log_access",
        "_order",
        "_check_company_domain",
    }

    # Field types and their patterns
    FIELD_TYPES: Dict[str, List[str]] = {
        "Many2one": ["fields.Many2one"],
        "One2many": ["fields.One2many"],
        "Many2many": ["fields.Many2many"],
        "Char": ["fields.Char"],
        "Text": ["fields.Text"],
        "Integer": ["fields.Integer"],
        "Float": ["fields.Float"],
        "Boolean": ["fields.Boolean"],
        "Date": ["fields.Date"],
        "Datetime": ["fields.Datetime"],
        "Selection": ["fields.Selection"],
        "Binary": ["fields.Binary"],
        "Html": ["fields.Html"],
        "Monetary": ["fields.Monetary"],
        "Reference": ["fields.Reference"],
        "Json": ["fields.Json"],
        "Image": ["fields.Image"],
    }

    # Field type priority order (AgroMarin standard)
    FIELD_TYPE_PRIORITY: Dict[str, int] = {
        "Char": 0,
        "Integer": 1,
        "Float": 2,
        "Boolean": 3,
        "Date": 4,
        "Datetime": 5,
        "Binary": 6,
        "Image": 7,
        "Selection": 8,
        "Html": 9,
        "Text": 10,
        "Many2one": 11,
        "One2many": 12,
        "Many2many": 13,
        "Monetary": 14,
        "Reference": 15,
        "Json": 16,
    }

    # Method patterns by category
    METHOD_PATTERNS: Dict[str, List[str]] = {
        "CRUD": [
            "create",
            "write",
            "unlink",
            "read",
            "copy",
            "copy_data",
            "default_get",
        ],
        "COMPUTE": ["_compute_", "compute_"],
        "INVERSE": ["_inverse_", "_set_"],
        "SEARCH": ["_search_"],
        "ONCHANGE": ["_onchange_", "onchange_"],
        "CONSTRAINTS": ["_check_", "_validate_", "_constrains_"],
        "ACTION": ["action_", "button_"],
        "OVERRIDE": ["name_get", "_compute_display_name", "fields_view_get"],
        "API_MODEL": [],  # Identified by @api.model decorator
    }

    # Decorator patterns
    DECORATOR_PATTERNS: Dict[str, List[str]] = {
        "COMPUTE": ["depends"],
        "ONCHANGE": ["onchange"],
        "CONSTRAINTS": ["constrains"],
        "MODEL": ["model", "model_create_multi"],
        "AUTOVACUUM": ["autovacuum"],
        "ONDELETE": ["ondelete"],
    }

    # Import group patterns
    IMPORT_PATTERNS: Dict[str, List[str]] = {
        "python_stdlib": [],  # Determined dynamically
        "odoo": ["odoo.", "odoo"],
        "odoo_addons": ["odoo.addons."],
        "third_party": [],  # Everything else
        "relative": [],  # Relative imports
    }

    # Section headers for organization
    SECTION_HEADERS: Dict[str, str] = {
        "MODEL_ATTRIBUTES": "CLASS ATTRIBUTES",
        "FIELDS": "FIELDS",
        "COMPUTED_FIELDS": "COMPUTED FIELDS",
        "SQL_CONSTRAINTS": "SQL CONSTRAINTS",
        "MODEL_INDEXES": "MODEL INDEXES",
        "CRUD": "CRUD METHODS",
        "COMPUTE": "COMPUTE METHODS",
        "ONCHANGE": "ONCHANGE METHODS",
        "CONSTRAINTS": "CONSTRAINT METHODS",
        "ACTION": "ACTION METHODS",
        "API_MODEL": "API MODEL METHODS",
        "BUSINESS": "BUSINESS METHODS",
        "PRIVATE": "PRIVATE METHODS",
        "MISC": "MISCELLANEOUS",
    }

    SEMANTIC_PATTERNS: Dict[str, Dict[str, List[str]]] = {
        "IDENTIFIERS": {
            "exact": ["name", "code", "default_code", "barcode", "ref", "reference"],
            "suffix": ["_ref", "_code", "_number"],
        },
        "ATTRIBUTES": {
            "exact": ["active", "sequence", "priority", "state", "type", "color"],
            "suffix": ["_state", "_type", "_mode"],
            "prefix": ["is_", "has_", "can_"],
        },
        "GENEALOGY": {
            "exact": ["parent_id", "parent_path", "child_id", "child_ids"],
            "suffix": ["_parent_id", "_child_id", "_child_ids"],
            "prefix": ["parent_", "child_"],
        },
        "RELATIONSHIPS": {
            "suffix": ["_id", "_ids"],
            "field_types": ["Many2one", "One2many", "Many2many"],
        },
        "MEASURES": {
            "exact": ["quantity", "price", "amount", "volume", "weight", "qty"],
            "suffix": ["_quantity", "_qty", "_amount", "_price", "_cost", "_total"],
            "prefix": ["total_", "sum_", "avg_"],
        },
        "DATES": {
            "exact": ["date", "datetime"],
            "suffix": ["_date", "_datetime", "_time", "_at"],
            "prefix": ["date_", "datetime_"],
        },
        "CONTENT": {
            "exact": ["description", "notes", "comment"],
            "suffix": ["_description", "_notes", "_text", "_html"],
            "field_types": ["Text", "Html"],
        },
    }
