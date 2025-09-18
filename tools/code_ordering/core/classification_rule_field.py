#!/usr/bin/env python3
"""
Field classification rules for the Ordering class.
Provides a rule-based system for classifying Odoo fields by their semantic meaning or type.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class FieldPriority(IntEnum):
    """Priority levels for field classification rules."""

    HIGHEST = 0  # Most specific rules (e.g., exact name matches)
    HIGH = 10  # Specific patterns (e.g., computed/related fields)
    MEDIUM = 20  # Common patterns (e.g., _id suffix for relationships)
    NORMAL = 30  # General patterns
    LOW = 40  # Generic patterns
    LOWEST = 50  # Catch-all rules


@dataclass
class ClassificationRuleField:
    """A single field classification rule."""

    category: str
    priority: int = FieldPriority.NORMAL

    # Pattern matching options
    exact_names: set[str] = field(default_factory=set)
    prefixes: set[str] = field(default_factory=set)
    suffixes: set[str] = field(default_factory=set)
    contains: set[str] = field(default_factory=set)
    field_types: set[str] = field(default_factory=set)

    # Special conditions
    check_computed: bool = False
    check_related: bool = False

    # Optional custom check function
    # Receives: (field_name, field_type, field_info_dict) -> bool
    custom_check: Callable[[str, str, dict[str, Any]], bool] | None = None

    def matches(
        self,
        field_name: str,
        field_info: dict[str, Any],
    ) -> bool:
        """Check if this rule matches the given field.

        Args:
            field_name: Name of the field
            field_type: Type of the field (Char, Many2one, etc.)
            field_info: Dictionary with field metadata (is_computed, is_related, etc.)

        Returns:
            bool: True if the rule matches
        """
        name_lower = field_name.lower()

        # Check special conditions first
        if self.check_computed and field_info.get("is_computed"):
            return True

        if self.check_related and field_info.get("is_related"):
            return True

        # Check field type
        if self.field_types and field_info.get("field_type") in self.field_types:
            # If custom_check exists, both must be true
            if self.custom_check:
                return self.custom_check(
                    field_name, field_info.get("field_type"), field_info
                )
            return True

        # Check exact name matches
        if field_name in self.exact_names or name_lower in self.exact_names:
            return True

        # Check prefixes
        for prefix in self.prefixes:
            if name_lower.startswith(prefix.lower()):
                return True

        # Check suffixes
        for suffix in self.suffixes:
            if name_lower.endswith(suffix.lower()):
                return True

        # Check contains
        for pattern in self.contains:
            if pattern.lower() in name_lower:
                return True

        # Check custom condition (when no other conditions are involved)
        if self.custom_check and not any(
            [
                self.field_types,
                self.exact_names,
                self.prefixes,
                self.suffixes,
                self.contains,
                self.check_computed,
                self.check_related,
            ],
        ):
            return self.custom_check(field_name, field_info)

        return False


def get_default_field_rules() -> list[ClassificationRuleField]:
    """Get the default set of field classification rules for semantic strategy.

    Returns rules that classify fields by their semantic meaning in the business domain.
    """
    rules = []

    # ============================================================
    # SPECIAL FIELDS (Highest Priority)
    # ============================================================

    # Computed fields take precedence
    rules.append(
        ClassificationRuleField(
            category="COMPUTED",
            priority=FieldPriority.HIGHEST,
            check_computed=True,
        ),
    )

    # Related fields
    rules.append(
        ClassificationRuleField(
            category="RELATED",
            priority=FieldPriority.HIGHEST,
            check_related=True,
        ),
    )

    # ============================================================
    # IDENTIFIERS (High Priority)
    # ============================================================

    rules.append(
        ClassificationRuleField(
            category="IDENTIFIERS",
            priority=FieldPriority.HIGH,
            exact_names={
                "name",
                "code",
                "default_code",
                "barcode",
                "ref",
                "reference",
                "display_name",
                "complete_name",
                "technical_name",
                "internal_reference",
                "sku",
                "ean",
                "ean13",
                "uuid",
                "token",
                "key",
                "slug",
            },
            suffixes={"_ref", "_code", "_number", "_key", "_token", "_uuid", "_sku"},
            contains={"reference", "identifier"},
        ),
    )

    # ============================================================
    # ATTRIBUTES (High Priority)
    # ============================================================

    rules.append(
        ClassificationRuleField(
            category="ATTRIBUTES",
            priority=FieldPriority.HIGH,
            exact_names={
                "active",
                "sequence",
                "priority",
                "state",
                "type",
                "color",
                "status",
                "stage_id",
                "category_id",
                "tag_ids",
                "label",
                "kind",
                "mode",
                "level",
                "grade",
                "rank",
            },
            suffixes={"_state", "_type", "_mode", "_status", "_stage", "_category"},
            prefixes={"is_", "has_", "can_", "allow_", "enable_", "show_", "hide_"},
        ),
    )

    # ============================================================
    # GENEALOGY (High Priority)
    # ============================================================

    rules.append(
        ClassificationRuleField(
            category="GENEALOGY",
            priority=FieldPriority.HIGH,
            exact_names={
                "parent_id",
                "parent_path",
                "child_ids",
                "parent_name",
                "parent_left",
                "parent_right",
            },
            suffixes={"_parent_id", "_child_id", "_child_ids"},
            prefixes={"parent_", "child_"},
        ),
    )

    # ============================================================
    # MEASURES (Medium Priority)
    # ============================================================

    rules.append(
        ClassificationRuleField(
            category="MEASURES",
            priority=FieldPriority.MEDIUM,
            exact_names={
                "quantity",
                "qty",
                "price",
                "amount",
                "total",
                "subtotal",
                "volume",
                "weight",
                "size",
                "length",
                "width",
                "height",
                "rate",
                "percentage",
                "discount",
                "tax",
                "cost",
                "margin",
            },
            suffixes={
                "_quantity",
                "_qty",
                "_amount",
                "_price",
                "_cost",
                "_total",
                "_rate",
                "_percent",
                "_weight",
                "_volume",
                "_sum",
                "_avg",
            },
            prefixes={"total_", "sum_", "avg_", "min_", "max_"},
            contains={"amount", "price", "cost", "quantity"},
        ),
    )

    # ============================================================
    # DATES (Medium Priority)
    # ============================================================

    rules.append(
        ClassificationRuleField(
            category="DATES",
            priority=FieldPriority.MEDIUM,
            exact_names={
                "date",
                "datetime",
                "date_start",
                "date_end",
                "date_from",
                "date_to",
                "create_date",
                "write_date",
                "date_done",
                "date_order",
                "date_invoice",
            },
            suffixes={"_date", "_datetime", "_time", "_at", "_on"},
            prefixes={"date_", "datetime_", "time_"},
            field_types={"Date", "Datetime"},
        ),
    )

    # ============================================================
    # CONTENT (Medium Priority)
    # ============================================================

    rules.append(
        ClassificationRuleField(
            category="CONTENT",
            priority=FieldPriority.MEDIUM,
            exact_names={
                "description",
                "notes",
                "note",
                "comment",
                "comments",
                "body",
                "content",
                "text",
                "message",
                "summary",
            },
            suffixes={"_description", "_notes", "_text", "_html", "_comment", "_body"},
            contains={"description", "comment", "note"},
            field_types={"Text", "Html"},
        ),
    )

    # ============================================================
    # USER & COMPANY (Medium Priority)
    # ============================================================

    rules.append(
        ClassificationRuleField(
            category="USER_COMPANY",
            priority=FieldPriority.MEDIUM,
            exact_names={
                "user_id",
                "create_uid",
                "write_uid",
                "company_id",
                "company_ids",
                "partner_id",
                "customer_id",
                "vendor_id",
                "supplier_id",
            },
            suffixes={"_user_id", "_uid", "_company_id", "_partner_id"},
            contains={"company", "user_id", "partner"},
        ),
    )

    # ============================================================
    # MONETARY (Medium Priority)
    # ============================================================

    rules.append(
        ClassificationRuleField(
            category="MONETARY",
            priority=FieldPriority.MEDIUM,
            field_types={"Monetary"},
            suffixes={"_amount", "_total", "_price", "_cost"},
        ),
    )

    # ============================================================
    # RELATIONSHIPS (Normal Priority - generic)
    # ============================================================

    rules.append(
        ClassificationRuleField(
            category="RELATIONSHIPS",
            priority=FieldPriority.NORMAL,
            field_types={"Many2one", "One2many", "Many2many"},
            suffixes={"_id", "_ids"},
        ),
    )

    # ============================================================
    # FILES & IMAGES (Normal Priority)
    # ============================================================

    rules.append(
        ClassificationRuleField(
            category="FILES",
            priority=FieldPriority.NORMAL,
            exact_names={
                "file",
                "attachment",
                "document",
                "image",
                "logo",
                "icon",
                "avatar",
                "picture",
                "photo",
                "thumbnail",
            },
            suffixes={"_file", "_attachment", "_image", "_document", "_logo"},
            field_types={"Binary", "Image"},
        ),
    )

    # ============================================================
    # TECHNICAL (Low Priority)
    # ============================================================

    rules.append(
        ClassificationRuleField(
            category="TECHNICAL",
            priority=FieldPriority.LOW,
            prefixes={"_", "technical_", "internal_", "system_", "debug_"},
            contains={"technical", "internal", "debug"},
        ),
    )

    # ============================================================
    # CATCH-ALL (Lowest Priority)
    # ============================================================

    rules.append(
        ClassificationRuleField(
            category="UNCATEGORIZED",
            priority=FieldPriority.LOWEST,
            custom_check=lambda name, ftype, info: True,  # Matches everything
        ),
    )

    # Sort rules by priority
    rules.sort(key=lambda r: r.priority)

    return rules
