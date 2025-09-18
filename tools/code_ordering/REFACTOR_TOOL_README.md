# Odoo Field Refactoring Tool Documentation

## Overview

The Odoo Field Refactoring Tool is designed to detect and fix naming convention violations in Odoo field definitions across your entire codebase. It was created to address inconsistencies in forked Odoo codebases where fields don't follow Odoo's naming guidelines.

### Tool Consolidation (Sept 2024)
This tool is the result of merging two previous implementations:
- `odoo_naming_refactor.py` (detection engine)
- `refactor_engine.py` (execution engine)

The unified `odoo_field_refactor.py` now includes all features in a single, more maintainable tool with enhanced pattern matching and confidence scoring.

## Problem Statement

In Odoo development, certain field types should follow specific naming conventions:
- **Many2one** fields should end with `_id` (e.g., `partner_id`, `product_id`)
- **One2many** fields should end with `_ids` (e.g., `line_ids`, `tag_ids`)
- **Many2many** fields should end with `_ids` (e.g., `category_ids`, `user_ids`)
- Field names should avoid redundancy (e.g., `purchase.order.order_line` → `purchase.order.line_ids`)

Manual refactoring of these violations is complex because:
1. Fields are referenced across multiple file types (Python, XML, CSV, JavaScript)
2. Changes require database migrations
3. Cross-module dependencies make it risky to change field names
4. Missing a single reference can break the system

## Architecture & Design

### Core Components

```
odoo_field_refactor.py
├── OdooFieldAnalyzer (AST-based Python analyzer)
│   ├── Detects field definitions in Python files
│   ├── Identifies naming violations
│   └── Suggests corrections based on rules
│
├── RefactorEngine (Refactoring executor)
│   ├── Finds all field references across codebase
│   ├── Applies transformations to Python/XML/CSV files
│   ├── Generates SQL migration scripts
│   └── Creates backups before modifications
│
└── OdooRefactorTool (Main orchestrator)
    ├── Module discovery and analysis
    ├── Violation filtering and reporting
    └── User interaction and confirmation
```

### Detection Process

1. **AST Analysis**: Parses Python files to find field definitions
2. **Pattern Matching**: Identifies violations based on field type and naming rules
3. **Cross-Reference Search**: Finds all usages across the codebase
4. **Impact Assessment**: Determines scope of changes needed

### Refactoring Process

1. **Backup Creation**: Saves original files with timestamp
2. **Python Refactoring**: Updates field definitions, decorators, and references
3. **XML Refactoring**: Updates views, domains, and contexts
4. **Migration Generation**: Creates SQL scripts for database changes
5. **Report Generation**: Documents all changes made

## Installation & Setup

```bash
# Navigate to the tools directory
cd /mnt/c/odoo/server/addons_custom/tools/code_ordering

# Make the script executable
chmod +x odoo_field_refactor.py

# Test the installation
python3 odoo_field_refactor.py --help
```

## Configuration for Multiple Addon Paths

The tool supports multiple addon directories which is common in Odoo deployments:

```bash
# Specify custom Odoo path and addon directories
python3 odoo_field_refactor.py \
    --odoo-path /mnt/c/odoo/server \
    --addon-paths /mnt/c/odoo/server/addons /mnt/c/odoo/enterprise /mnt/c/odoo/server/addons_custom \
    --analyze

# Using default paths (automatically searches for addons, addons_enterprise, addons_custom)
python3 odoo_field_refactor.py --analyze

# For separate enterprise repository
python3 odoo_field_refactor.py \
    --addon-paths /path/to/odoo/addons /path/to/enterprise-repo /path/to/custom-addons \
    --analyze
```

## Usage Guide

### Basic Commands

#### 1. Analyze for Violations

```bash
# Analyze all modules
python3 odoo_field_refactor.py --analyze

# Analyze specific module
python3 odoo_field_refactor.py --analyze --module purchase

# Analyze multiple modules
python3 odoo_field_refactor.py --analyze --modules sale purchase stock
```

#### 2. Single Field Refactoring

```bash
# Refactor a specific field (dry run by default)
python3 odoo_field_refactor.py --refactor \
    --field order_line \
    --new-name line_ids \
    --module purchase

# Execute the refactoring (actually modify files)
python3 odoo_field_refactor.py --refactor \
    --field order_line \
    --new-name line_ids \
    --module purchase \
    --execute
```

#### 3. Batch Refactoring

```bash
# Fix all violations in a module (with confirmation)
python3 odoo_field_refactor.py --refactor --module sale --execute

# Fix all violations without confirmation
python3 odoo_field_refactor.py --refactor --module sale --batch --execute
```

### Command-Line Options

| Option | Description | Example |
|--------|-------------|---------|
| `--odoo-path PATH` | Base path to Odoo installation | `--odoo-path /mnt/c/odoo/server` |
| `--addon-paths LIST` | Custom addon directories to scan | `--addon-paths /path/to/addons /path/to/enterprise` |
| `--analyze` | Show violations without making changes | `--analyze` |
| `--refactor` | Execute refactoring operations | `--refactor` |
| `--field FIELD` | Target specific field name | `--field order_line` |
| `--new-name NAME` | Specify new name for field | `--new-name line_ids` |
| `--model MODEL` | Target specific model | `--model purchase.order` |
| `--module MODULE` | Target specific module | `--module purchase` |
| `--modules LIST` | Target multiple modules | `--modules sale purchase` |
| `--exclude LIST` | Exclude modules from analysis | `--exclude test_module` |
| `--dry-run` | Preview changes without modifying | (default) |
| `--execute` | Actually modify files | `--execute` |
| `--no-backup` | Skip backup creation | `--no-backup` |
| `--no-migration` | Skip SQL migration generation | `--no-migration` |
| `--batch` | Process without confirmation | `--batch` |

## Real-World Examples

### Example 1: Fix order_line Field Across Purchase and Sale

```bash
# First, analyze to see the violations (with custom addon paths)
python3 odoo_field_refactor.py \
    --addon-paths /mnt/c/odoo/server/addons /mnt/c/odoo/enterprise \
    --analyze --field order_line --modules purchase sale

# Output:
# Using addon paths: /mnt/c/odoo/server/addons, /mnt/c/odoo/enterprise
# Found 2 naming violations:
# purchase.order.order_line -> line_ids (redundant_prefix)
# sale.order.order_line -> line_ids (redundant_prefix)

# Execute the refactoring
python3 odoo_field_refactor.py \
    --addon-paths /mnt/c/odoo/server/addons /mnt/c/odoo/enterprise \
    --refactor \
    --field order_line \
    --new-name line_ids \
    --modules purchase sale \
    --execute

# Output:
# Refactoring purchase.order.order_line -> line_ids
#   Modified 147 references
# Refactoring sale.order.order_line -> line_ids
#   Modified 235 references
# ✓ Refactoring complete!
#   Files modified: 52
#   Migration script: migration_order_line_20250917_194126.sql
```

### Example 2: Fix Many2one Missing Suffix

```bash
# Analyze for Many2one violations
python3 odoo_field_refactor.py --analyze --module hr

# Fix specific field
python3 odoo_field_refactor.py --refactor \
    --field manager \
    --new-name manager_id \
    --model hr.employee \
    --execute
```

### Example 3: Refactor Enterprise Module Fields

```bash
# Analyze enterprise-specific modules
python3 odoo_field_refactor.py \
    --addon-paths /mnt/c/odoo/enterprise /mnt/c/odoo/server/addons \
    --analyze --module planning

# Refactor a specific field in enterprise module
python3 odoo_field_refactor.py \
    --addon-paths /mnt/c/odoo/enterprise /mnt/c/odoo/server/addons \
    --refactor \
    --field planning_slot \
    --new-name slot_ids \
    --module planning \
    --execute
```

### Example 4: Clean Up Entire Module

```bash
# See all violations in a module
python3 odoo_field_refactor.py --analyze --module stock

# Fix all violations with review
python3 odoo_field_refactor.py --refactor --module stock --execute

# Fix all violations automatically (batch mode)
python3 odoo_field_refactor.py --refactor --module stock --batch --execute
```

## Enhanced Pattern Detection

The tool now includes sophisticated pattern matching for common Odoo naming issues:

### Pattern-Based Detection (High Confidence: 0.95)
- `*_order_line` → `line_ids`
- `*_invoice_line` → `line_ids`
- `*_purchase_line` → `line_ids`
- `*_sale_line` → `line_ids`
- `*_move_line` → `line_ids`
- `*_stock_move` → `move_ids`
- `*_product_line` → `line_ids`
- `*_delivery_line` → `line_ids`
- `*_timesheet_line` → `line_ids`
- `*_payment_line` → `line_ids`

## Detected Violation Types

### 1. Pattern Violation (Highest Priority)
```python
# Before
purchase_order_line = fields.One2many(...)  # Matches pattern

# After
line_ids = fields.One2many(...)
```

### 2. Missing Suffix
```python
# Before
partner = fields.Many2one('res.partner')  # Missing _id
lines = fields.One2many('sale.order.line', 'order_id')  # Missing _ids

# After
partner_id = fields.Many2one('res.partner')
line_ids = fields.One2many('sale.order.line', 'order_id')
```

### 2. Redundant Prefix
```python
# Before (in purchase.order)
purchase_order_line = fields.One2many(...)  # Redundant "purchase_order"

# After
line_ids = fields.One2many(...)
```

### 3. Boolean Prefix (Future Enhancement)
```python
# Before
active_status = fields.Boolean()

# After
is_active = fields.Boolean()
```

## Generated Files

### 1. Migration Script
```sql
-- migration_order_line_20250917_194126.sql
ALTER TABLE purchase_order
RENAME COLUMN order_line TO line_ids;

UPDATE ir_model_fields
SET name = 'line_ids'
WHERE model = 'purchase.order'
  AND name = 'order_line';
```

### 2. Refactoring Report
```json
{
  "timestamp": "2025-09-17T19:41:26",
  "violations_found": 2,
  "changes_made": 382,
  "violations": [...],
  "changes": [
    {
      "file": "addons/purchase/models/purchase_order.py",
      "old_name": "order_line",
      "new_name": "line_ids",
      "type": "definition"
    }
  ]
}
```

### 3. Backup Directory
```
backup_20250917_194126/
├── addons/
│   ├── purchase/
│   │   └── models/
│   │       └── purchase_order.py.bak
│   └── sale/
│       └── models/
│           └── sale_order.py.bak
```

## Safety Features

1. **Dry Run Mode** (default): Shows changes without modifying files
2. **Backup System**: Creates timestamped backups before changes
3. **Confirmation Prompts**: Requires explicit confirmation unless in batch mode
4. **Migration Scripts**: Generates SQL for database schema updates
5. **Comprehensive Reports**: JSON report of all changes made
6. **Rollback Capability**: Backups allow manual rollback if needed

## Common Patterns Fixed

### Pattern 1: API Decorators
```python
# Before
@api.depends('order_line.price_subtotal')

# After
@api.depends('line_ids.price_subtotal')
```

### Pattern 2: Field Access
```python
# Before
for line in self.order_line:

# After
for line in self.line_ids:
```

### Pattern 3: XML Views
```xml
<!-- Before -->
<field name="order_line" widget="one2many_list">

<!-- After -->
<field name="line_ids" widget="one2many_list">
```

### Pattern 4: Domain Filters
```xml
<!-- Before -->
<field name="partner_id" domain="[('order_line.state', '=', 'draft')]"/>

<!-- After -->
<field name="partner_id" domain="[('line_ids.state', '=', 'draft')]"/>
```

## Troubleshooting

### Issue: Changes Not Applied
- Ensure using `--execute` flag (default is dry-run)
- Check file permissions
- Verify module path is correct

### Issue: Tests Failing After Refactoring
- Run generated migration SQL on test database
- Clear cache: `odoo-bin --stop-after-init`
- Update test fixtures that reference old field names

### Issue: Missing References
- Tool searches common patterns but may miss:
  - JavaScript files with dynamic field access
  - SQL queries in custom methods
  - External integrations
- Manual review recommended for critical fields

## Best Practices

1. **Always Start with Analysis**
   ```bash
   python3 odoo_field_refactor.py --analyze --module target_module
   ```

2. **Test on Development First**
   - Run refactoring on development environment
   - Execute migration scripts
   - Run full test suite
   - Then apply to production

3. **Refactor by Module**
   - Process one module at a time
   - Test thoroughly between modules
   - Commit changes incrementally

4. **Review Generated Migrations**
   - Check SQL scripts before execution
   - Add any custom migration logic needed
   - Test rollback procedures

5. **Document Changes**
   - Keep refactoring reports
   - Update module documentation
   - Notify team of field name changes

## Limitations

1. **Dynamic Field Access**: May not catch dynamically constructed field names
2. **JavaScript**: Limited support for JS files (basic pattern matching only)
3. **Custom SQL**: Won't update raw SQL queries in Python strings
4. **External Systems**: Can't update external integrations automatically
5. **Computed Field Stores**: May need manual cache clearing after rename

## Future Enhancements

- [ ] Boolean field prefix standardization (is_, has_, use_)
- [ ] Method naming convention enforcement
- [ ] Support for JavaScript refactoring with proper AST
- [ ] Integration with Odoo upgrade scripts
- [ ] Automated test suite updates
- [ ] Git integration for automatic commits
- [ ] Parallel processing for large codebases
- [ ] Custom naming rule configuration

## Support & Contribution

For issues or improvements:
1. Check the refactoring report for detailed change logs
2. Review backup files if rollback needed
3. Enhance detection patterns in `OdooFieldAnalyzer`
4. Add new refactoring patterns in `RefactorEngine`

## Working with Multiple Repositories

When your Odoo installation uses multiple repositories (common with Enterprise):

```bash
# Directory structure example:
# /mnt/c/odoo/
# ├── server/
# │   ├── addons/           (Community addons)
# │   └── addons_custom/    (Your custom modules)
# └── enterprise/           (Separate Enterprise repo)

# Analyze across all repositories
python3 odoo_field_refactor.py \
    --addon-paths \
        /mnt/c/odoo/server/addons \
        /mnt/c/odoo/enterprise \
        /mnt/c/odoo/server/addons_custom \
    --analyze

# Refactor a field that might exist in multiple repos
python3 odoo_field_refactor.py \
    --addon-paths \
        /mnt/c/odoo/server/addons \
        /mnt/c/odoo/enterprise \
    --field order_line \
    --new-name line_ids \
    --execute
```

### Path Resolution Priority

1. If `--addon-paths` is specified, only those paths are used
2. If `--odoo-path` is specified without `--addon-paths`, it searches for:
   - `{odoo_path}/addons`
   - `{odoo_path}/addons_enterprise`
   - `{odoo_path}/addons_custom`
3. The tool automatically filters out non-existent paths
4. Module search follows the order of addon paths provided

## License

Internal tool for Odoo codebase maintenance. Use with caution on production systems.