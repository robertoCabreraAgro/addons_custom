# Odoo Field Refactoring Tool

A comprehensive tool for renaming fields across the entire Odoo codebase while maintaining consistency and generating migration scripts.

## Features

- Detects naming violations based on Odoo field naming conventions
- Refactors fields across Python, XML, JavaScript, and YAML files
- Generates SQL migration scripts
- Creates backups before modifications
- Provides detailed reports of changes

## Usage

### Analyze naming violations

```bash
# Analyze all modules for naming violations
python3 odoo_field_refactor.py --analyze

# Analyze specific module
python3 odoo_field_refactor.py --analyze --module sale

# Analyze specific field
python3 odoo_field_refactor.py --analyze --field order_line
```

### Refactor fields

```bash
# Rename order_line to line_ids in sale module (dry-run by default)
python3 odoo_field_refactor.py --refactor --field order_line --new-name line_ids --module sale

# Actually execute the refactoring (not dry-run)
python3 odoo_field_refactor.py --refactor --field order_line --new-name line_ids --module sale --execute

# Refactor across multiple modules
python3 odoo_field_refactor.py --refactor --field order_line --new-name line_ids --modules sale purchase stock --execute

# Batch mode (no confirmation prompts)
python3 odoo_field_refactor.py --refactor --field order_line --new-name line_ids --batch --execute
```

## Supported Patterns

The tool handles the following patterns across different file types:

### Python Files
- Field definitions: `order_line = fields.One2many(...)`
- Decorator parameters: `@api.depends('order_line.price_total')`
- Direct access: `self.order_line`
- Method calls: `order_line.filtered()`, `order_line.mapped()`
- Loops: `for line in order.order_line:`
- Lambda expressions: `lambda x: x.order_line`
- Dictionary keys: `{'order_line': value}`
- Domain expressions: `[('order_line.product_id', '=', False)]`
- Comments and docstrings

### XML Files
- Field elements: `<field name="order_line"/>`
- Domain/context attributes: `domain="[('order_line.product_id', 'ilike', self)]"`
- QWeb templates: `t-field="order.order_line"`
- XPath expressions

### JavaScript Files
- Object property access: `order.order_line`
- Method chaining: `order.order_line.map()`
- Template literals: `${order.order_line}`
- JSX attributes
- Comments

### YAML Files
- Keys and values
- List items
- Comments

## Options

- `--dry-run` (default): Show what would be changed without modifying files
- `--execute`: Actually modify files
- `--no-backup`: Skip creating backups
- `--no-migration`: Skip generating SQL migration scripts
- `--batch`: Process without confirmation prompts

## Migration Scripts

The tool automatically generates SQL migration scripts that:
- Rename database columns
- Update `ir_model_fields` records
- Update stored filters and actions

Example migration script:
```sql
-- Migration script for sale.order.order_line -> line_ids
ALTER TABLE sale_order
RENAME COLUMN order_line TO line_ids;

UPDATE ir_model_fields
SET name = 'line_ids'
WHERE model = 'sale.order'
AND name = 'order_line';
```

## Safety Features

1. **Dry-run by default**: Always shows what would be changed before actual modification
2. **Backup creation**: Creates timestamped backups before modifications
3. **Detailed reports**: Saves JSON reports of all changes
4. **Pattern validation**: Uses comprehensive regex patterns to ensure accurate replacements

## Example: Renaming order_line to line_ids

```bash
# Step 1: Analyze the current state
python3 odoo_field_refactor.py --analyze --field order_line

# Step 2: Dry-run to see what would change
python3 odoo_field_refactor.py --refactor --field order_line --new-name line_ids --modules sale purchase

# Step 3: Execute the refactoring
python3 odoo_field_refactor.py --refactor --field order_line --new-name line_ids --modules sale purchase --execute

# Step 4: Review the generated migration script and report
ls -la migration_order_line_*.sql
cat refactor_report_*.json
```

## Requirements

- Python 3.8+
- Access to Odoo source code
- Write permissions for backup and report generation