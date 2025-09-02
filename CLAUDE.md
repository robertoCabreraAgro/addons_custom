# CLAUDE.md - AgroMarin Addons

## Pre-Work Check
**⚠️ ALWAYS: Before working on any module, check if README.md exists in the module directory and read it thoroughly for specific instructions, configurations, or considerations.**

## Quick Context
- **Platform**: Odoo 18.0 (saas-18.2), Python 3.11+, PostgreSQL with PostGIS
- **Repository**: 40+ custom Odoo modules for agricultural ERP with Mexican localization
- **Task System**: Every change requires Task ID from `/planning/` directory
- **Branch Format**: `18.2-t<TASK_ID>-<INITIALS>`

## Critical Odoo 18.0 Changes
```xml
<!-- Views -->
<list> instead of <tree>
<chatter /> instead of <div class="oe_chatter">...</div>
invisible="state == 'draft'" instead of attrs="{'invisible': [('state', '=', 'draft')]}"
<app> and <block> for settings views
group_ids not groups_id in ir.ui.menu

<!-- Python -->
_compute_display_name() replaces name_get()
_search_display_name() replaces _name_search()
_has_cycle() replaces _check_recursion()
self.env.user.has_group() replaces user_has_groups()
check_access() unifies check_access_rights() and check_access_rule()
```

## Commands
```bash
# Module operations
./odoo-bin -u module_name -d db_name              # Update module
./odoo-bin -u module_name -d db_name --test-enable # Run tests
./odoo-bin shell -d db_name                       # Interactive shell

# Development
./odoo-bin scaffold module_name /path/to/addons   # Create module
./odoo-bin -d db_name --dev=all                   # Debug mode
```

## AgroMarin Coding Standards

### Field Declaration Order (STRICT)
```python
class Model(models.Model):
    # 1. Char
    name = fields.Char()
    # 2. Integer
    priority = fields.Integer()
    # 3. Float
    amount = fields.Float()
    # 4. Boolean
    active = fields.Boolean()
    # 5. Date
    date = fields.Date()
    # 6. Datetime
    datetime = fields.Datetime()
    # 7. Binary
    file = fields.Binary()
    # 8. Image
    image = fields.Image()
    # 9. Selection
    state = fields.Selection()
    # 10. Html
    description_html = fields.Html()
    # 11. Text
    notes = fields.Text()
    # 12. Many2one
    partner_id = fields.Many2one()
    # 13. One2many
    line_ids = fields.One2many()
    # 14. Many2many
    tag_ids = fields.Many2many()
    # 15. Monetary
    price = fields.Monetary()
    # 16. Related
    partner_name = fields.Related()
    # 17. Computed
    total = fields.Float(compute="_compute_total")
    # 18. Reference
    ref = fields.Reference()
```

### Method Order (STRICT)
```python
class Model(models.Model):
    # 1. Constructors
    def create(self, vals):
    def write(self, vals):
    def unlink(self):
    
    # 2. Computed (@api.depends)
    def _compute_total(self):
    
    # 3. Onchange (@api.onchange)
    def _onchange_partner(self):
    
    # 4. Validations (@api.constrains, _check_*, _validate_*)
    def _check_date(self):
    
    # 5. Actions (action_*)
    def action_confirm(self):
    
    # 6. Business Logic (_do_*, _post_*)
    def _post_invoice(self):
    
    # 7. Helpers (_get_*, _prepare_*, _find_*)
    def _prepare_invoice_line(self):
    
    # 8. Tools (format_*, calculate_*)
    def format_reference(self):
    
    # 9. Integrations (_call_*, _sync_*)
    def _call_sat_api(self):
```

### Mandatory Practices
- **English only** for all code, comments, variables
- **Docstrings required** for all methods and classes
- **Double quotes** for all strings
- **Type hints** where applicable
- **Tests** for business logic

### Docstring Template
```python
def method_name(self, param1, param2):
    """Brief description of what the method does.
    
    Args:
        param1 (type): Description
        param2 (type): Description
        
    Returns:
        type: Description
        
    Raises:
        ValidationError: When validation fails
    """
```

## Module Structure
```
module_name/
├── __manifest__.py      # Dependencies: base, stock, sale, etc.
├── models/             # One file per model
├── views/              # XML views (use record ids: view_model_form)
├── security/           # ir.model.access.csv, security rules
├── data/              # Default data
├── tests/             # Test classes inheriting TransactionCase
└── i18n/              # Translations (es_MX.po primary)
```

## Task Workflow
1. Check `/planning/<TASK_ID>.md` for requirements
2. **Check if module has README.md and read it**
3. Create branch: `18.2-t<TASK_ID>-<INITIALS>`
4. Implement following all standards above
5. Include tests and documentation
6. Update module version in `__manifest__.py`

## Common Patterns
```python
# Record creation with context
with self.env.cr.savepoint():
    record = self.env['model'].with_context(skip_validation=True).create(vals)

# Batch operations
self.env['model'].search([]).filtered(lambda r: r.active)._process_batch()

# Mexican tax calculation
self.env['l10n_mx.edi.document']._get_cfdi_values()
```

## Testing Requirements
- Use `TransactionCase` for database operations
- Test Mexican fiscal validations
- Cover agricultural business cases
- Mock external API calls (SAT, GPS services)

## File References
- See `/planning/` for task specifications
- Check `marin/__manifest__.py` for full dependency tree
- Review `l10n_mx_edi*/` for Mexican compliance examples