# Code Refactoring Proposal: Eliminating Redundancies

## Overview
This proposal outlines how to refactor the code_ordering module to eliminate redundancies by using shared mixins and base classes.

## Identified Redundancies

### 1. AST Analysis Operations
**Files affected:** `odoo_field_refactor.py`, `odoo_reorder.py`, `core/ordering.py`

**Redundant code:**
- `_is_odoo_model()` - Checking if a class is an Odoo model
- `_get_model_name()` - Extracting model name from _name/_inherit
- `_is_field_assignment()` - Checking if assignment is a field
- `_snake_case()` - Converting CamelCase to snake_case

### 2. Configuration Management
**Files affected:** `odoo_field_refactor.py`, `odoo_reorder.py`

**Redundant code:**
- Config dataclasses with similar fields
- JSON loading/saving logic
- Default value management

### 3. File Operations
**Files affected:** `odoo_field_refactor.py`, `odoo_reorder.py`

**Redundant code:**
- Backup creation logic
- File reading/writing patterns
- Dry-run handling

### 4. Constants and Patterns
**Files affected:** All three files

**Redundant code:**
- Field type definitions (Char, Text, Integer, etc.)
- Model attribute lists (_name, _inherit, etc.)
- Decorator patterns

## Refactoring Strategy

### Phase 1: Create Shared Base Module ✅
Created `core/base_mixins.py` containing:
- `OdooConstants` - Centralized constants
- `OdooASTMixin` - Common AST operations
- `BackupMixin` - File backup operations
- `BaseConfig` - Base configuration class
- `NamingUtilsMixin` - Naming utilities
- `ReportMixin` - Report generation
- `ModulePathMixin` - Module path handling
- `DecoratorMixin` - Decorator utilities

### Phase 2: Refactor Existing Files

#### 2.1 Refactor `odoo_field_refactor.py`

**Before:**
```python
class OdooFieldAnalyzer(ast.NodeVisitor):
    FIELD_TYPES = {...}  # Duplicate constants

    def _is_odoo_model(self, node):  # Duplicate method
        ...

    def _snake_case(self, name):  # Duplicate method
        ...
```

**After:**
```python
from core.base_mixins import OdooASTMixin, OdooConstants, NamingUtilsMixin

class OdooFieldAnalyzer(ast.NodeVisitor, OdooASTMixin, NamingUtilsMixin):
    # Remove FIELD_TYPES, use OdooConstants.FIELD_TYPES
    # Remove _is_odoo_model(), inherited from OdooASTMixin
    # Remove _snake_case(), inherited from NamingUtilsMixin

    def visit_ClassDef(self, node):
        if self.is_odoo_model(node):  # Use inherited method
            model_name = self.get_model_name(node)  # Use inherited method
            ...
```

#### 2.2 Refactor `odoo_reorder.py`

**Before:**
```python
@dataclass
class Config:
    create_backup: bool = True
    dry_run: bool = False
    # ... duplicate config fields
```

**After:**
```python
from core.base_mixins import BaseConfig

@dataclass
class ReorderConfig(BaseConfig):
    # Only add reorder-specific fields
    field_strategy: str = "semantic"
    method_groups: list = field(default_factory=list)
```

#### 2.3 Refactor `core/ordering.py`

**Before:**
```python
class Ordering:
    MODEL_ATTRIBUTES: list[str] = [...]  # Duplicate constants

    def _get_default_config(self):  # Duplicate config logic
        ...
```

**After:**
```python
from core.base_mixins import OdooConstants, BaseConfig

class Ordering:
    # Use OdooConstants.MODEL_ATTRIBUTES instead of defining own

    def __init__(self, config=None, ...):
        self.config = config or BaseConfig()  # Use base config
```

### Phase 3: Create Specialized Mixins

#### 3.1 Create `OdooFieldMixin`
```python
class OdooFieldMixin(OdooASTMixin):
    """Specialized mixin for field-specific operations."""

    def get_field_info(self, node: ast.Assign) -> Dict:
        """Extract comprehensive field information."""
        # Combine logic from multiple files

    def classify_field(self, field_info: Dict) -> str:
        """Classify field by type and semantics."""
        # Unified field classification logic
```

#### 3.2 Create `OdooMethodMixin`
```python
class OdooMethodMixin(OdooASTMixin):
    """Specialized mixin for method-specific operations."""

    def classify_method(self, node: ast.FunctionDef) -> str:
        """Classify method by its purpose."""
        # Unified method classification logic
```

## Implementation Benefits

### 1. Code Reduction
- **Estimated reduction:** ~30-40% less code
- **Lines saved:** ~500-700 lines

### 2. Maintainability
- Single source of truth for each functionality
- Easier to fix bugs (fix once, apply everywhere)
- Consistent behavior across tools

### 3. Extensibility
- New tools can easily inherit common functionality
- Add new features to mixin = available to all tools

### 4. Testing
- Test mixins once, confidence in all tools
- Reduced test duplication

## Migration Plan

### Step 1: Update Imports (Low Risk)
```python
# Add to each file
from core.base_mixins import (
    OdooASTMixin, BackupMixin, BaseConfig,
    NamingUtilsMixin, OdooConstants
)
```

### Step 2: Inherit Mixins (Low Risk)
```python
# Update class definitions
class OdooFieldAnalyzer(ast.NodeVisitor, OdooASTMixin, NamingUtilsMixin):
```

### Step 3: Remove Redundant Code (Medium Risk)
- Remove duplicate methods
- Remove duplicate constants
- Update method calls to use inherited versions

### Step 4: Test Thoroughly (Required)
```bash
# Run tests for each tool
python3 odoo_field_refactor.py --analyze --module sale
python3 odoo_reorder.py test_file.py --dry-run
python3 -m pytest tests/
```

## Backwards Compatibility

All changes maintain backwards compatibility:
- Public APIs remain unchanged
- Command-line interfaces unchanged
- Output formats unchanged

## Example Usage After Refactoring

```python
# Creating a new tool becomes trivial
from core.base_mixins import OdooASTMixin, BackupMixin, BaseConfig

class NewOdooTool(OdooASTMixin, BackupMixin):
    def __init__(self, config: BaseConfig = None):
        self.config = config or BaseConfig()

    def analyze_file(self, filepath: Path):
        # Automatically have access to:
        # - is_odoo_model()
        # - get_model_name()
        # - create_backup()
        # - All other mixin methods
        pass
```

## Risk Assessment

- **Low Risk:** Using mixins for utilities (snake_case, backup)
- **Medium Risk:** Refactoring AST operations (well-tested patterns)
- **Low Risk:** Config consolidation (backwards compatible)

## Timeline

- Phase 1: ✅ Complete (base_mixins.py created)
- Phase 2: 2-3 hours (refactor existing files)
- Phase 3: 1-2 hours (create specialized mixins)
- Testing: 1 hour

## Recommendation

Proceed with the refactoring in phases:
1. Start with low-risk changes (imports, inheritance)
2. Test each change incrementally
3. Keep backup of original files
4. Document any behavioral changes

This refactoring will significantly improve code maintainability while preserving all existing functionality.