"""
Dependency Analysis for Code Elements.

Analyzes dependencies between fields and methods to enable
intelligent code organization.
"""

import ast
from collections import defaultdict

from .ordering import Ordering


class DependencyAnalyzer:
    """Analyzes dependencies between fields and methods."""

    def __init__(self, processor: Ordering):
        self.processor = processor
        self.field_dependencies = defaultdict(set)
        self.method_dependencies = defaultdict(set)

    def analyze_field_dependencies(
        self, class_node: ast.ClassDef
    ) -> dict[str, set[str]]:
        """
        Analyze dependencies between fields.

        Identifies:
        - Related fields and their base fields
        - Computed fields and their compute methods

        Args:
            class_node: AST node of the class to analyze

        Returns:
            Dict mapping field names to their dependencies
        """
        dependencies = defaultdict(set)

        for node in ast.walk(class_node):
            if isinstance(node, ast.Assign):
                if hasattr(node, "targets") and node.targets:
                    target = node.targets[0]
                    if isinstance(target, ast.Name):
                        field_name = target.id

                        # Check for related fields
                        if isinstance(node.value, ast.Call):
                            for keyword in node.value.keywords:
                                if keyword.arg == "related":
                                    # Extract related field
                                    if isinstance(keyword.value, ast.Constant):
                                        related = keyword.value.value
                                        base_field = related.split(".")[0]
                                        dependencies[field_name].add(base_field)

                                elif keyword.arg == "compute":
                                    # Extract compute method
                                    if isinstance(keyword.value, ast.Constant):
                                        compute_method = keyword.value.value
                                        dependencies[field_name].add(compute_method)

        return dependencies

    def analyze_method_dependencies(
        self, class_node: ast.ClassDef
    ) -> dict[str, set[str]]:
        """
        Analyze dependencies between methods.

        Identifies method calls within each method to build
        a dependency graph.

        Args:
            class_node: AST node of the class to analyze

        Returns:
            Dict mapping method names to methods they call
        """
        dependencies = defaultdict(set)

        for node in ast.walk(class_node):
            if isinstance(node, ast.FunctionDef):
                method_name = node.name

                # Find method calls within this method
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Attribute):
                            if isinstance(child.func.value, ast.Name):
                                if child.func.value.id == "self":
                                    called_method = child.func.attr
                                    dependencies[method_name].add(called_method)

        return dependencies

    def analyze_all_dependencies(
        self, class_node: ast.ClassDef
    ) -> dict[str, dict[str, set[str]]]:
        """
        Analyze all dependencies in a class.

        Args:
            class_node: AST node of the class to analyze

        Returns:
            Dict with 'fields' and 'methods' dependency mappings
        """
        return {
            "fields": self.analyze_field_dependencies(class_node),
            "methods": self.analyze_method_dependencies(class_node),
        }

    def get_dependency_order(self, dependencies: dict[str, set[str]]) -> list[str]:
        """
        Get topological ordering based on dependencies.

        Args:
            dependencies: Dependency mapping

        Returns:
            List of names in dependency order
        """
        # Build reverse dependencies
        reverse_deps = defaultdict(set)
        all_items = set(dependencies.keys())

        for item, deps in dependencies.items():
            all_items.update(deps)
            for dep in deps:
                reverse_deps[dep].add(item)

        # Find items with no dependencies
        no_deps = [
            item
            for item in all_items
            if item not in dependencies or not dependencies[item]
        ]
        ordered = []

        while no_deps:
            # Take item with no dependencies
            item = no_deps.pop(0)
            ordered.append(item)

            # Remove this item from dependencies of others
            for dependent in reverse_deps[item]:
                dependencies[dependent].discard(item)
                if not dependencies[dependent]:
                    no_deps.append(dependent)

        # Add any remaining items (cycles)
        remaining = all_items - set(ordered)
        ordered.extend(sorted(remaining))

        return ordered
