# CLAUDE.md - AgroMarin Addons

## Pre-Work Check
**⚠️ ALWAYS: Before working on any module, check if README.md exists in the module directory and read it thoroughly for specific instructions, configurations, or considerations.**

## Quick Context
- **Platform**: Odoo 18.0 (saas-18.2), Python 3.11+, PostgreSQL with PostGIS
- **Repository**: 40+ custom Odoo modules for agricultural ERP with Mexican localization
- **Task System**: Every change requires Task ID from `/home/<USER>/instancias/planning/` directory
- **Branch Format**: `18.2-t<TASK_ID>-<INITIALS>`
- **Coding Standard**: Use `pre-commit-vauxoo` to check quality, consistency and adherence to project standards
- **Commit Messages**:
   - Use conventional format: `[TAG] module: description`
   - Tags: IMP (improvement), FIX (bug fix), ADD (new feature), REF (refactor)
   - Keep messages concise but descriptive
   - Maximum 80 characters per line

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
    def action_confirm(self):   - Write messages in English
    
    # 9. Integrations (_call_*, _sync_*)
    def _call_sat_api(self):
```

### Mandatory Practices
- **English only** for all code, comments, variables
- **Docstrings required** for all methods and classes
- **Double quotes** for all strings

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
## File naming
Odoo modules follow a standardized structure to facilitate navigation and code maintenance. Let's use an `agriculture_management` module as example with main models: `farm.field` and `harvest.order`.

**Models (`/models/`)**
- One file per main model: `farm_field.py`, `harvest_order.py`
- Inherited models in separate files: `res_partner.py`, `product_product.py`
- If only one model exists, use the module name

**Security (`/security/`)**
Three main files:
- `ir.model.access.csv` - Access rights definition
- `agriculture_management_groups.xml` - User groups (farmers, supervisors, managers)
- `farm_field_security.xml`, `harvest_order_security.xml` - Record rules per model

**Views (`/views/`)**
- Backend views: `farm_field_views.xml`, `harvest_order_views.xml`
- Main menus: `agriculture_management_menus.xml` (optional)
- QWeb templates: `harvest_order_templates.xml` (portal/reports)
- Inherited views: `res_partner_views.xml`

**Data (`/data/`)**
Split by purpose and model:
- `farm_field_data.xml` - Initial data (crop types, seasons)
- `harvest_order_demo.xml` - Demo data
- `mail_data.xml` - Email templates for harvest notifications

**Controllers (`/controllers/`)**
- Main controller: `agriculture_management.py` (avoid `main.py`)
- Inherited controllers: `portal.py` (for farmer portal access)

**Wizards (`/wizard/`)**
- `crop_planning_wizard.py`
- `crop_planning_wizard_views.xml`

**Reports (`/report/`)**
- Statistical reports: `harvest_analysis_report.py`, `harvest_analysis_report_views.xml`
- Printable reports:
  - `harvest_order_reports.xml` (actions, paperformat)
  - `harvest_order_templates.xml` (QWeb templates)

## Task Workflow
1. Check `/home/<USER>/instancias/planning/<TASK_ID>.md` for requirements
2. **Check if module has README.md and read it**
3. Create branch: `18.2-t<TASK_ID>-<INITIALS>`
4. Run `pre-commit-vauxoo -t all -p <MODULE_NAME>`
5. Create commit(s): `[TAG] module: description`
6. Update module version in `__manifest__.py`

## File References
- See `/home/<USER>/instancias/planning/` for task specifications
- Check `marin/__manifest__.py` for full dependency tree
- Review `l10n_mx_edi*/` for Mexican compliance examples