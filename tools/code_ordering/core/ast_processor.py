"""
Base AST processor providing common AST operations.

This module provides a foundation for all AST-related operations,
eliminating duplication across the codebase.
"""

import ast
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

from .base_patterns import setup_logging
from .unified_cache import UnifiedCache

logger = setup_logging(__name__)


class BaseASTProcessor:
    """
    Base class for AST processing operations.

    Provides common functionality for parsing, extracting, and analyzing
    Python AST nodes. This eliminates duplication across tools.
    """

    def __init__(
        self, content: str, filepath: Optional[Path] = None, use_cache: bool = True
    ):
        """
        Initialize AST processor.

        Args:
            content: Python source code content
            filepath: Optional path to the source file
            use_cache: Whether to use AST caching
        """
        self.content = content
        self.filepath = filepath
        self.use_cache = use_cache
        self._tree = None
        self._lines = None
        self._cache = UnifiedCache()

        if use_cache:
            cached = self._cache.get_ast(content)
            if cached:
                self._tree, self._lines = cached
                logger.debug(f"Using cached AST for {filepath or 'content'}")

    @property
    def tree(self) -> ast.Module:
        """Get the parsed AST tree, parsing if necessary."""
        if self._tree is None:
            self.parse()
        return self._tree

    @property
    def lines(self) -> List[str]:
        """Get the source lines."""
        if self._lines is None:
            self._lines = self.content.splitlines()
        return self._lines

    def parse(self) -> None:
        """Parse the content into an AST tree."""
        try:
            self._tree = ast.parse(self.content)
            if self.use_cache:
                self._cache.set_ast(self.content, self._tree, self.lines)
            logger.debug(f"Successfully parsed {self.filepath or 'content'}")
        except SyntaxError as e:
            logger.error(f"Syntax error parsing {self.filepath or 'content'}: {e}")
            raise

    def extract_imports(self) -> List[ast.stmt]:
        """Extract all import statements."""
        imports = []
        for node in self.tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imports.append(node)
        return imports

    def extract_classes(self) -> List[ast.ClassDef]:
        """Extract all top-level class definitions."""
        return [node for node in self.tree.body if isinstance(node, ast.ClassDef)]

    def extract_functions(self) -> List[Union[ast.FunctionDef, ast.AsyncFunctionDef]]:
        """Extract all top-level function definitions."""
        return [
            node
            for node in self.tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

    def extract_assignments(self) -> List[ast.Assign]:
        """Extract all top-level assignments (module-level variables)."""
        return [node for node in self.tree.body if isinstance(node, ast.Assign)]

    def extract_class_elements(
        self, class_node: ast.ClassDef
    ) -> Dict[str, List[ast.AST]]:
        """
        Extract elements from a class definition.

        Returns:
            Dictionary with keys: 'methods', 'fields', 'properties', 'class_vars'
        """
        elements = {
            "methods": [],
            "fields": [],
            "properties": [],
            "class_vars": [],
            "decorators": [],
        }

        for node in class_node.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check if it's a property
                if self._is_property(node):
                    elements["properties"].append(node)
                else:
                    elements["methods"].append(node)
            elif isinstance(node, ast.Assign):
                elements["fields"].append(node)
            elif isinstance(node, ast.AnnAssign):
                elements["fields"].append(node)
            elif isinstance(node, (ast.ClassDef,)):
                # Nested classes
                elements["class_vars"].append(node)

        # Add class decorators
        elements["decorators"] = class_node.decorator_list

        return elements

    def _is_property(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> bool:
        """Check if a function is decorated as a property."""
        for decorator in node.decorator_list:
            decorator_name = self.extract_decorator_name(decorator)
            if decorator_name and "property" in decorator_name:
                return True
        return False

    @staticmethod
    def extract_decorator_name(decorator: ast.expr) -> Optional[str]:
        """Extract the name from a decorator node."""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            return decorator.attr
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name):
                return decorator.func.id
            elif isinstance(decorator.func, ast.Attribute):
                return decorator.func.attr
        return None

    @staticmethod
    def get_node_name(node: ast.AST) -> Optional[str]:
        """Get the name of an AST node if it has one."""
        if hasattr(node, "name"):
            return node.name
        elif isinstance(node, ast.Assign):
            targets = []
            for target in node.targets:
                if isinstance(target, ast.Name):
                    targets.append(target.id)
                elif isinstance(target, ast.Tuple):
                    for elt in target.elts:
                        if isinstance(elt, ast.Name):
                            targets.append(elt.id)
            return ", ".join(targets) if targets else None
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            return node.target.id
        return None

    @staticmethod
    def unparse_safe(node: ast.AST, fallback: str = "") -> str:
        """Safely unparse an AST node to source code."""
        try:
            return ast.unparse(node)
        except Exception as e:
            logger.debug(f"Failed to unparse node: {e}")
            return fallback

    def get_docstring(
        self,
        node: Union[ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef, ast.Module],
    ) -> Optional[str]:
        """Extract docstring from a node."""
        return ast.get_docstring(node)

    def get_line_range(self, node: ast.AST) -> Tuple[int, int]:
        """Get the line range (start, end) for a node."""
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            return (node.lineno, node.end_lineno or node.lineno)
        elif hasattr(node, "lineno"):
            return (node.lineno, node.lineno)
        return (0, 0)

    def get_source_segment(self, node: ast.AST) -> Optional[str]:
        """Get the source code segment for a node."""
        try:
            return ast.get_source_segment(self.content, node)
        except Exception:
            # Fallback to line-based extraction
            start_line, end_line = self.get_line_range(node)
            if start_line > 0 and end_line > 0:
                return "\n".join(self.lines[start_line - 1 : end_line])
        return None

    @lru_cache(maxsize=128)
    def find_imports_for_name(self, name: str) -> List[ast.stmt]:
        """Find import statements that import a specific name."""
        imports = []
        for node in self.extract_imports():
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == name or (alias.asname and alias.asname == name):
                        imports.append(node)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == name or (alias.asname and alias.asname == name):
                        imports.append(node)
        return imports

    def extract_all_names(self) -> Set[str]:
        """Extract all defined names in the module."""
        names = set()

        # Classes
        for cls in self.extract_classes():
            if cls.name:
                names.add(cls.name)

        # Functions
        for func in self.extract_functions():
            if func.name:
                names.add(func.name)

        # Module-level variables
        for assign in self.extract_assignments():
            name = self.get_node_name(assign)
            if name:
                names.add(name)

        return names

    def safe_unparse(self, node: ast.AST, fallback: str = "") -> str:
        """
        Safely unparse an AST node to source code.

        Args:
            node: AST node to unparse
            fallback: Fallback value if unparsing fails

        Returns:
            Source code string or fallback
        """
        try:
            return ast.unparse(node)
        except Exception as e:
            logger.debug(f"Failed to unparse node: {e}")
            return fallback

    def get_decorator_source(self, decorator: ast.expr) -> str:
        """
        Get the source representation of a decorator.

        Args:
            decorator: Decorator AST node

        Returns:
            Decorator source with @ prefix
        """
        decorator_segment = self.get_source_segment(decorator)
        if decorator_segment:
            return f"@{decorator_segment}"
        else:
            # Fallback to unparsing
            return f"@{self.safe_unparse(decorator)}"

    def get_full_decorator_name(self, decorator: ast.expr) -> str:
        """
        Get the full name of a decorator including module path.

        Args:
            decorator: Decorator AST node

        Returns:
            Full decorator name (e.g., 'api.model')
        """
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            parts = []
            node = decorator
            while isinstance(node, ast.Attribute):
                parts.append(node.attr)
                node = node.value
            if isinstance(node, ast.Name):
                parts.append(node.id)
            return ".".join(reversed(parts))
        elif isinstance(decorator, ast.Call):
            return self.get_full_decorator_name(decorator.func)
        return ""

    def extract_decorators(
        self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef]
    ) -> List[str]:
        """
        Extract all decorator names from a node.

        Args:
            node: Node with decorators

        Returns:
            List of decorator names
        """
        decorators = []
        for decorator in node.decorator_list:
            full_name = self.get_full_decorator_name(decorator)
            if full_name:
                decorators.append(full_name)
        return decorators

    def is_decorated_with(
        self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef], patterns: Set[str]
    ) -> bool:
        """
        Check if a node has decorators matching any of the patterns.

        Args:
            node: Function or method node
            patterns: Set of decorator patterns to match

        Returns:
            True if any decorator matches
        """
        decorators = self.extract_decorators(node)
        for decorator in decorators:
            for pattern in patterns:
                if pattern in decorator or pattern.lstrip("@") in decorator:
                    return True
        return False

    def get_node_type(self, node: ast.AST) -> str:
        """Get the type name of an AST node."""
        return node.__class__.__name__

    def find_nodes_by_type(
        self, node_type: type, root: Optional[ast.AST] = None
    ) -> List[ast.AST]:
        """
        Find all nodes of a specific type in the tree.

        Args:
            node_type: Type of nodes to find
            root: Root node to search from (default: self.tree)

        Returns:
            List of matching nodes
        """
        root = root or self.tree
        return [node for node in ast.walk(root) if isinstance(node, node_type)]

    def get_node_location(self, node: ast.AST) -> str:
        """
        Get the location of a node as a string.

        Args:
            node: AST node

        Returns:
            Location string (e.g., 'file.py:10:5')
        """
        filename = self.filepath.name if self.filepath else "<string>"
        if hasattr(node, "lineno") and hasattr(node, "col_offset"):
            return f"{filename}:{node.lineno}:{node.col_offset}"
        elif hasattr(node, "lineno"):
            return f"{filename}:{node.lineno}"
        return filename
