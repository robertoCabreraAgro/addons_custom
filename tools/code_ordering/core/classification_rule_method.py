#!/usr/bin/env python3
"""
Method classification rules for the Ordering class.
Separate file to keep the rules organized and maintainable.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import IntEnum


class Priority(IntEnum):
    """Priority levels for classification rules."""

    HIGHEST = 0
    HIGH = 10
    MEDIUM = 20
    NORMAL = 30
    LOW = 40
    LOWEST = 50


@dataclass
class ClassificationRuleMethod:
    """A single method classification rule."""

    category: str
    priority: int = Priority.NORMAL

    # Pattern matching options
    exact_matches: set[str] = field(default_factory=set)
    prefixes: set[str] = field(default_factory=set)
    contains: set[str] = field(default_factory=set)
    decorators: set[str] = field(default_factory=set)

    # Optional custom check function
    custom_check: Callable[[str, list[str]], bool] | None = None

    def matches(
        self,
        method_name: str,
        decorator_list: list[str],
    ) -> bool:
        """Check if this rule matches the given method."""
        # Check decorators first (usually most specific)
        if self.decorators:
            decorator_matched = False
            for decorator in decorator_list:
                decorator_name = decorator.strip("@")
                # Exact match for decorators to avoid "model" matching "model_create_multi"
                if decorator_name in self.decorators:
                    decorator_matched = True
                    break

            # If decorator matched and there's a custom_check, both must be true
            if decorator_matched:
                if self.custom_check:
                    return self.custom_check(method_name, decorator_list)
                return True

        # Check exact matches
        if method_name in self.exact_matches:
            return True

        # Check prefixes
        for prefix in self.prefixes:
            if method_name.startswith(prefix):
                return True

        # Check contains
        for pattern in self.contains:
            if pattern in method_name:
                return True

        # Check custom condition (when no decorators are involved)
        if self.custom_check and not self.decorators:
            return self.custom_check(method_name, decorator_list)

        return False


def get_default_method_rules() -> list[ClassificationRuleMethod]:
    """Get the default set of method classification rules."""
    rules = []
    crud_method_names = {
        "create",
        "write",
        "unlink",
        "read",
        "copy",
        "copy_data",
        "default_get",
        "name_create",
    }
    search_method_names = {
        "name_search",
        "_name_search",
        "_search_display_name",
    }
    excluded_from_api_model = crud_method_names | search_method_names

    # ============================================================
    # DECORATOR-BASED RULES (Highest Priority)
    # ============================================================

    rules.append(
        ClassificationRuleMethod(
            category="COMPUTE",
            priority=Priority.HIGHEST,
            decorators={"depends", "depends_context"},
        ),
    )

    rules.append(
        ClassificationRuleMethod(
            category="ONCHANGE",
            priority=Priority.HIGHEST,
            decorators={"onchange"},
        ),
    )

    rules.append(
        ClassificationRuleMethod(
            category="CONSTRAINT",
            priority=Priority.HIGHEST,
            decorators={"constrains"},
        ),
    )

    # API_MODEL - but exclude CRUD and SEARCH methods even if they have @api.model
    # In Odoo, CRUD and SEARCH methods often have @api.model but should remain in their categories

    rules.append(
        ClassificationRuleMethod(
            category="API_MODEL",
            priority=Priority.HIGHEST,
            decorators={"model"},
            custom_check=lambda name, _: name not in excluded_from_api_model,
        ),
    )

    rules.append(
        ClassificationRuleMethod(
            category="AUTOVACUUM",
            priority=Priority.HIGHEST,
            decorators={"autovacuum"},
        ),
    )

    # ============================================================
    # SPECIFIC PATTERNS (High Priority)
    # ============================================================

    # Workflow methods
    rules.append(
        ClassificationRuleMethod(
            category="WORKFLOW",
            priority=Priority.HIGH,
            exact_matches={
                "action_draft",
                "action_confirm",
                "action_validate",
                "action_approve",
                "action_done",
                "action_cancel",
                "action_reject",
                "action_send",
                "action_post",
                "action_reset",
            },
        ),
    )

    # CRUD methods
    rules.append(
        ClassificationRuleMethod(
            category="CRUD",
            priority=Priority.HIGH,
            exact_matches=crud_method_names,
            decorators={"model_create_multi", "ondelete"},
        ),
    )

    # Override methods
    rules.append(
        ClassificationRuleMethod(
            category="OVERRIDE",
            priority=Priority.HIGH,
            exact_matches={
                "name_get",
                "_compute_display_name",
                "fields_view_get",
                "fields_get",
                "load_views",
            },
        ),
    )

    # ============================================================
    # MIXIN-SPECIFIC PATTERNS (High Priority)
    # ============================================================

    # Product Catalog Mixin
    rules.append(
        ClassificationRuleMethod(
            category="PRODUCT_CATALOG",
            priority=Priority.HIGH,
            exact_matches={"action_add_from_catalog"},
            prefixes={
                "_get_product_catalog_",
                "_get_action_add_from_catalog_",
                "_create_section",
                "_get_sections",
                "_resequence_sections",
                "_get_new_line_sequence",
                "_get_default_create_section_",
                "_is_line_valid_for_section",
                "_is_display_stock_in_catalog",
            },
            contains={"_product_catalog_"},
        ),
    )

    # Mail Thread
    rules.append(
        ClassificationRuleMethod(
            category="MAIL_THREAD",
            priority=Priority.HIGH,
            exact_matches={
                "message_post",
                "message_subscribe",
                "message_unsubscribe",
                "message_route",
                "message_update",
                "message_new",
            },
            prefixes={
                "_message_",
                "_track_",
                "_routing_",
                "_notify_",
                "_follow_",
                "_unfollow_",
                "_subscribe_",
                "_unsubscribe_",
                "_activity_",
            },
        ),
    )

    # ============================================================
    # PATTERN-BASED RULES (Normal Priority)
    # ============================================================

    rules.append(
        ClassificationRuleMethod(
            category="COMPUTE",
            priority=Priority.MEDIUM,
            prefixes={"_compute_"},  # Specific compute pattern
        ),
    )

    rules.append(
        ClassificationRuleMethod(
            category="INVERSE",
            priority=Priority.MEDIUM,  # Specific inverse pattern
            prefixes={"_inverse_", "_set_"},
        ),
    )

    rules.append(
        ClassificationRuleMethod(
            category="SEARCH",
            priority=Priority.MEDIUM,  # Specific search pattern
            prefixes={"_search_"},
            exact_matches={"name_search", "_name_search", "_search_display_name"},
        ),
    )

    rules.append(
        ClassificationRuleMethod(
            category="ONCHANGE",
            priority=Priority.MEDIUM,
            prefixes={"_onchange_"},  # Specific onchange pattern
        ),
    )

    rules.append(
        ClassificationRuleMethod(
            category="CONSTRAINT",
            priority=Priority.MEDIUM,  # Specific constraint patterns
            prefixes={"_check_", "_validate_", "_constrains_"},
        ),
    )

    rules.append(
        ClassificationRuleMethod(
            category="PREPARE",
            priority=Priority.NORMAL,
            prefixes={"_prepare_"},
        ),
    )

    rules.append(
        ClassificationRuleMethod(
            category="GETTER",
            priority=Priority.LOW,  # Generic getter - lower priority than specific patterns
            prefixes={"_get_", "get_", "_get_default_"},
        ),
    )

    rules.append(
        ClassificationRuleMethod(
            category="REPORT",
            priority=Priority.MEDIUM,  # More specific than generic getter
            prefixes={"_get_report_", "_render_"},
            exact_matches={"get_report_values"},
        ),
    )

    rules.append(
        ClassificationRuleMethod(
            category="IMPORT_EXPORT",
            priority=Priority.NORMAL,
            prefixes={"_import_", "_export_"},
            exact_matches={"action_import", "action_export"},
        ),
    )

    rules.append(
        ClassificationRuleMethod(
            category="SECURITY",
            priority=Priority.NORMAL,
            prefixes={"_check_access_", "has_group"},
            exact_matches={"check_access"},
        ),
    )

    rules.append(
        ClassificationRuleMethod(
            category="VALIDATION",
            priority=Priority.NORMAL,
            prefixes={"can_", "_is_", "is_"},
        ),
    )

    rules.append(
        ClassificationRuleMethod(
            category="PORTAL",
            priority=Priority.NORMAL,
            prefixes={"_prepare_portal_", "portal_"},
        ),
    )

    rules.append(
        ClassificationRuleMethod(
            category="COMMUNICATION",
            priority=Priority.NORMAL,
            prefixes={"_send_", "_mail_", "_sms_"},
            contains={"_notify_"},
        ),
    )

    rules.append(
        ClassificationRuleMethod(
            category="WIZARD",
            priority=Priority.NORMAL,
            prefixes={"_process_", "do_"},
            exact_matches={"action_apply"},
        ),
    )

    rules.append(
        ClassificationRuleMethod(
            category="INTEGRATION",
            priority=Priority.NORMAL,
            prefixes={"_sync_", "_api_", "_call_"},
        ),
    )

    rules.append(
        ClassificationRuleMethod(
            category="CRON",
            priority=Priority.NORMAL,
            prefixes={"_cron_", "_scheduled_"},
        ),
    )

    rules.append(
        ClassificationRuleMethod(
            category="ACCOUNTING",
            priority=Priority.NORMAL,
            prefixes={"_reconcile_", "_post_", "_move_", "_compute_balance_"},
        ),
    )

    rules.append(
        ClassificationRuleMethod(
            category="MANUFACTURING",
            priority=Priority.NORMAL,
            prefixes={"_explode_", "_produce_", "_consume_"},
        ),
    )

    # ============================================================
    # GENERIC PATTERNS (Low Priority)
    # ============================================================

    # Generic actions (should be checked after specific action patterns)
    rules.append(
        ClassificationRuleMethod(
            category="ACTIONS", priority=Priority.LOW, prefixes={"action_", "button_"}
        ),
    )

    # ============================================================
    # CATCH-ALL RULES (Lowest Priority)
    # ============================================================

    rules.append(
        ClassificationRuleMethod(
            category="PRIVATE",
            priority=Priority.LOWEST,
            custom_check=lambda name, _: name.startswith("_"),
        ),
    )

    rules.append(
        ClassificationRuleMethod(
            category="PUBLIC",
            priority=Priority.LOWEST,
            custom_check=lambda name, _: not name.startswith("_"),
        ),
    )

    # Sort rules by priority
    rules.sort(key=lambda r: r.priority)

    return rules
