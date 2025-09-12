#!/usr/bin/env python3
"""
Sorting Utilities for Code Ordering

Provides common sorting algorithms and utilities used across the code ordering system.

Author: Agromarin Tools
Version: 1.0.0
"""

import ast
from typing import Dict, List, Optional, Any, Callable
from core import BaseASTProcessor


class TopologicalSorter:
    """Performs topological sorting on dependency graphs."""

    @staticmethod
    def sort(graph: Dict[str, List[str]]) -> List[str]:
        """
        Perform topological sort on dependency graph.

        Args:
            graph: Dictionary mapping nodes to their dependencies

        Returns:
            List of nodes in topologically sorted order
        """
        # Calculate in-degree for each node
        in_degree = {node: 0 for node in graph}
        for deps in graph.values():
            for dep in deps:
                if dep in in_degree:
                    in_degree[dep] += 1

        # Queue for nodes with no dependencies
        queue = [node for node, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            # Sort queue for stable ordering
            queue.sort()
            node = queue.pop(0)
            result.append(node)

            # Reduce in-degree for dependent nodes
            for dep in graph.get(node, []):
                if dep in in_degree:
                    in_degree[dep] -= 1
                    if in_degree[dep] == 0:
                        queue.append(dep)

        # Add any remaining nodes (cycles or disconnected)
        for node in graph:
            if node not in result:
                result.append(node)

        return result


class FieldSorter:
    """Provides field sorting utilities."""

    # Unified field type order (Odoo conventions)
    FIELD_TYPE_ORDER = {
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
        None: 99,
    }

    @classmethod
    def get_type_priority(
        cls, field_type: Optional[str], is_computed: bool = False
    ) -> int:
        """
        Get sorting priority for a field type.

        Args:
            field_type: The field type name
            is_computed: Whether the field is computed

        Returns:
            Integer priority for sorting
        """
        if field_type in cls.FIELD_TYPE_ORDER:
            return cls.FIELD_TYPE_ORDER[field_type]
        else:
            return 99

    @staticmethod
    def sort_by_name_with_suffix(
        items: List[tuple], name_index: int = 0
    ) -> List[tuple]:
        """
        Sort items considering _id/_ids suffix grouping.

        Args:
            items: List of tuples containing field information
            name_index: Index of the name in the tuple

        Returns:
            Sorted list of items
        """

        def sort_key(item):
            name = item[name_index]
            # Handle _id/_ids suffix for proper grouping
            if name.endswith("_ids"):
                base = name[:-4]
                suffix_order = 1
            elif name.endswith("_id"):
                base = name[:-3]
                suffix_order = 0
            else:
                base = name
                suffix_order = 2
            return (base.lower(), suffix_order)

        return sorted(items, key=sort_key)

    @staticmethod
    def sort_alphabetically(fields: List[Any], get_name_func) -> List[Any]:
        """Sort fields alphabetically by name only."""
        field_info = []

        # Collect field names
        for field_node in fields:
            field_name = get_name_func(field_node)
            if field_name:
                field_info.append((field_name, field_node))

        # Sort alphabetically by field name
        field_info.sort(key=lambda item: item[0].lower())
        return [node for _, node in field_info]

    @staticmethod
    def sort_genealogy(fields: List[Any], get_name_func) -> List[Any]:
        """Sort genealogy fields in specific order: parent_id, parent_path, child_id, child_ids."""
        # Define the preferred order for genealogy fields
        genealogy_order = ["parent_id", "parent_path", "child_id", "child_ids"]

        # Create a dictionary to store fields by name
        field_dict = {}
        other_fields = []

        for field_node in fields:
            field_name = get_name_func(field_node)
            if field_name:
                field_dict[field_name] = field_node
                if field_name not in genealogy_order:
                    other_fields.append(field_node)

        # Build result list in preferred order
        result = []
        for field_name in genealogy_order:
            if field_name in field_dict:
                result.append(field_dict[field_name])

        # Add any remaining genealogy fields sorted alphabetically
        other_fields.sort(key=lambda node: get_name_func(node) or "")
        result.extend(other_fields)

        return result

    @staticmethod
    def sort_relationship(fields: List[Any], get_name_func, get_type_func) -> List[Any]:
        """Sort relationship fields: Many2one first, then One2many, then Many2many."""
        # Categorize fields by relationship type
        many2one_fields = []
        one2many_fields = []
        many2many_fields = []
        other_fields = []

        for field_node in fields:
            field_type = get_type_func(field_node)
            field_name = get_name_func(field_node)

            if field_type == "Many2one":
                many2one_fields.append((field_name, field_node))
            elif field_type == "One2many":
                one2many_fields.append((field_name, field_node))
            elif field_type == "Many2many":
                many2many_fields.append((field_name, field_node))
            else:
                other_fields.append(field_node)

        # Sort each category using suffix-aware sorting
        many2one_fields = FieldSorter.sort_by_name_with_suffix(
            many2one_fields, name_index=0
        )
        one2many_fields = FieldSorter.sort_by_name_with_suffix(
            one2many_fields, name_index=0
        )
        many2many_fields = FieldSorter.sort_by_name_with_suffix(
            many2many_fields, name_index=0
        )

        # Build result
        result = [node for _, node in many2one_fields]
        result.extend([node for _, node in one2many_fields])
        result.extend([node for _, node in many2many_fields])

        # Add any other fields
        other_fields.sort(key=lambda node: get_name_func(node) or "")
        result.extend(other_fields)

        return result

    @staticmethod
    def sort_by_type_and_name(
        fields: List[Any], get_name_func, get_type_func
    ) -> List[Any]:
        """Sort fields by type then alphabetically."""
        field_info = []

        # Collect field information
        for field_node in fields:
            field_name = get_name_func(field_node)
            field_type = get_type_func(field_node)
            if field_name:
                field_info.append((field_name, field_type, field_node))

        # First sort by type priority
        for i, (name, field_type, node) in enumerate(field_info):
            priority = FieldSorter.get_type_priority(field_type, is_computed=False)
            field_info[i] = (name, field_type, node, priority)

        # Group by type priority
        from itertools import groupby

        field_info.sort(key=lambda x: x[3])  # Sort by priority first
        grouped = []
        for priority, group in groupby(field_info, key=lambda x: x[3]):
            # Within each type group, use suffix-aware sorting
            group_list = [
                (name, field_type, node) for name, field_type, node, _ in group
            ]
            sorted_group = FieldSorter.sort_by_name_with_suffix(
                group_list, name_index=0
            )
            grouped.extend(sorted_group)

        field_info = grouped
        return [node for _, _, node in field_info]

    @staticmethod
    def sort_strict(
        fields: List[Any], get_name_func, get_type_func, is_computed_func
    ) -> List[Any]:
        """Sort fields using AgroMarin strict ordering standards."""
        field_info = []

        # Collect field information
        for field_node in fields:
            field_name = get_name_func(field_node)
            field_type = get_type_func(field_node)
            is_computed = is_computed_func(field_node)
            if field_name:
                field_info.append((field_name, field_type, is_computed, field_node))

        def get_sort_key(item):
            field_name, field_type, is_computed, _ = item
            priority = FieldSorter.get_type_priority(field_type, is_computed)
            return (priority, field_name.lower())

        field_info.sort(key=get_sort_key)
        return [node for _, _, _, node in field_info]

    @staticmethod
    def organize_with_related(
        fields: List[Any], get_name_func, extract_info_func
    ) -> List[Any]:
        """Organize fields placing related fields next to their base fields."""
        from collections import defaultdict

        # Separate fields into base fields and related fields
        base_fields = []
        related_fields = defaultdict(list)  # base_field_name -> [related_fields]
        orphan_related_fields = []

        for field_node in fields:
            field_info = extract_info_func(field_node)
            field_name = field_info.get("field_name")
            is_related = field_info.get("is_related", False)
            related_field_base = field_info.get("related_field_base")

            if is_related and related_field_base:
                # Check if the base field exists in our current field list
                base_exists = any(
                    get_name_func(f) == related_field_base for f in fields
                )
                if base_exists:
                    related_fields[related_field_base].append(field_node)
                else:
                    # Base field doesn't exist in current group
                    orphan_related_fields.append(field_node)
            else:
                base_fields.append(field_node)

        # Build the result list
        result = []
        for field_node in base_fields:
            field_name = get_name_func(field_node)
            result.append(field_node)

            # Add related fields immediately after their base field
            if field_name in related_fields:
                related_list = related_fields[field_name]
                # Sort related fields alphabetically if there are multiple
                if len(related_list) > 1:
                    related_list.sort(key=lambda f: get_name_func(f) or "")
                result.extend(related_list)

        # Add orphan related fields at the end
        result.extend(orphan_related_fields)

        return result


class MethodSorter:
    """Provides method sorting utilities."""

    # Standard CRUD method order
    CRUD_METHOD_ORDER = [
        "create",
        "write",
        "unlink",
        "read",
        "copy",
        "copy_data",
        "default_get",
    ]

    @classmethod
    def sort_crud_methods(
        cls, methods: List[Any], name_attr: str = "name"
    ) -> List[Any]:
        """
        Sort CRUD methods in standard order.

        Args:
            methods: List of method objects
            name_attr: Attribute name to get method name

        Returns:
            Sorted list of methods
        """

        def get_order(method):
            name = getattr(method, name_attr, "").lower()
            try:
                return cls.CRUD_METHOD_ORDER.index(name)
            except ValueError:
                return 99

        return sorted(
            methods, key=lambda m: (get_order(m), getattr(m, name_attr, "").lower())
        )

    @staticmethod
    def _extract_depends_fields(decorator: ast.AST) -> List[str]:
        """Extract field dependencies from @api.depends decorator."""
        fields = []
        if isinstance(decorator, ast.Call):
            for arg in decorator.args:
                if isinstance(arg, ast.Constant):
                    fields.append(arg.value)
        return fields

    @staticmethod
    def _extract_onchange_fields(decorator: ast.AST) -> List[str]:
        """Extract field dependencies from @api.onchange decorator."""
        fields = []
        if isinstance(decorator, ast.Call):
            for arg in decorator.args:
                if isinstance(arg, ast.Constant):
                    fields.append(arg.value)
        return fields

    @staticmethod
    def _build_dependency_graph(
        methods: List[ast.AST], processor: BaseASTProcessor
    ) -> Dict[str, List[str]]:
        """Build dependency graph for compute and onchange methods based on @api.depends and @api.onchange."""
        graph = {}
        method_map = {m.name: m for m in methods}
        for method in methods:
            deps = []
            if hasattr(method, "decorator_list") and method.decorator_list:
                for decorator in method.decorator_list:
                    decorator_name = processor.extract_decorator_name(decorator) or ""
                    if "depends" in decorator_name:
                        field_deps = MethodSorter._extract_depends_fields(decorator)
                        # Check if any dependency is computed by another method
                        for field in field_deps:
                            # Look for compute method for this field
                            compute_method_name = f"_compute_{field}"
                            if compute_method_name in method_map:
                                deps.append(compute_method_name)
                    elif "onchange" in decorator_name:
                        field_deps = MethodSorter._extract_onchange_fields(decorator)
                        # Check if any dependency field has its own onchange method
                        for field in field_deps:
                            # Look for onchange method for this field
                            onchange_method_names = [
                                f"_onchange_{field}",
                                f"onchange_{field}",
                            ]
                            for onchange_name in onchange_method_names:
                                if (
                                    onchange_name in method_map
                                    and onchange_name != method.name
                                ):
                                    deps.append(onchange_name)
            graph[method.name] = deps
        return graph

    @classmethod
    def sort_topological_methods(
        cls, methods: List[Any], dependency_graph: Dict[str, List[str]] = None
    ) -> List[Any]:
        """
        Sort compute methods using topological sort if dependencies provided.
        Methods without decorators come first, then decorated methods.

        Args:
            methods: List of method objects
            dependency_graph: Optional dependency graph for topological sorting

        Returns:
            Sorted list of methods
        """
        # Separate methods into those with and without decorators
        non_decorated = []
        decorated = []

        for method in methods:
            has_decorator = False
            if hasattr(method, "decorator_list") and method.decorator_list:
                has_decorator = True

            if has_decorator:
                decorated.append(method)
            else:
                non_decorated.append(method)

        # Sort non-decorated methods alphabetically
        non_decorated.sort(key=lambda m: m.name.lower())

        # Sort decorated methods
        if dependency_graph and decorated:
            # Use topological sort for methods with dependencies
            sorted_names = TopologicalSorter.sort(dependency_graph)
            method_map = {m.name: m for m in decorated}

            # Reorder methods based on topological sort
            sorted_decorated = []
            for name in sorted_names:
                if name in method_map:
                    sorted_decorated.append(method_map[name])

            # Add any decorated methods not in the graph
            for method in decorated:
                if method not in sorted_decorated:
                    sorted_decorated.append(method)

            decorated = sorted_decorated
        else:
            # Simple alphabetical sort if no dependencies
            decorated.sort(key=lambda m: m.name.lower())

        # Return non-decorated first, then decorated
        return non_decorated + decorated


class AlphabeticalSorter:
    """Provides alphabetical sorting with various options."""

    @staticmethod
    def sort_case_insensitive(
        items: List[Any], key_func: Optional[Callable] = None
    ) -> List[Any]:
        """
        Sort items alphabetically, case-insensitive.

        Args:
            items: List of items to sort
            key_func: Optional function to extract sort key

        Returns:
            Sorted list of items
        """
        if key_func:
            return sorted(items, key=lambda x: key_func(x).lower())
        else:
            return sorted(items, key=lambda x: str(x).lower())

    @staticmethod
    def sort_with_priority(
        items: List[Any], priority_items: List[str], key_func: Optional[Callable] = None
    ) -> List[Any]:
        """
        Sort items alphabetically with some items prioritized.

        Args:
            items: List of items to sort
            priority_items: Items that should appear first
            key_func: Optional function to extract sort key

        Returns:
            Sorted list with priority items first
        """
        priority = []
        regular = []

        for item in items:
            key = key_func(item) if key_func else str(item)
            if key in priority_items:
                priority.append(item)
            else:
                regular.append(item)

        # Sort each group
        priority = AlphabeticalSorter.sort_case_insensitive(priority, key_func)
        regular = AlphabeticalSorter.sort_case_insensitive(regular, key_func)

        return priority + regular
