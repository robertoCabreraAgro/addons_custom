# Base EDI Module Analysis

## Current Structure Analysis

### Files Present
```
base_edi/
├── __init__.py
├── __manifest__.py
├── docs/
│   └── ROADMAP.md
└── models/
    ├── __init__.py
    ├── edi_certificate.py
    ├── edi_document.py
    ├── edi_format.py
    └── edi_provider.py
```

### Missing Components
Based on `models/__init__.py`, the following files are imported but don't exist:
- `edi_validator.py`
- `edi_workflow.py`
- `edi_document_manager.py`
- `res_company.py`
- `res_config_settings.py`

Also missing from `__manifest__.py` data references:
- `security/base_edi_security.xml`
- `security/ir.model.access.csv`
- `views/edi_document_views.xml`
- `views/edi_provider_views.xml`
- `views/edi_workflow_views.xml`
- `views/certificate_views.xml`
- `views/res_config_settings_views.xml`
- `data/edi_format_data.xml`

## Pattern Analysis

### 1. Model Design Patterns

#### Abstract vs Concrete Models
- **Abstract Models** (`models.AbstractModel`):
  - `base.edi.document` - Base class for inheritance
  - `base.edi.format` - Base class for country-specific formats

- **Concrete Models** (`models.Model`):
  - `edi.provider` - Actual database table
  - `certificate.certificate` (inherited) - Extended with EDI features

**Pattern**: Use abstract models for base functionality that will be extended by country modules, concrete models for shared resources.

#### Inheritance Strategy
- `_inherit` for extending existing models (e.g., `certificate.certificate`)
- `_name` with `_inherit` for abstract base classes
- Clear separation between base functionality and country-specific implementation

### 2. Field Patterns

#### State Management
```python
processing_stage = fields.Selection([
    ('draft', 'Draft'),
    ('validated', 'Validated'),
    ('signed', 'Signed'),
    ('sent', 'Sent to Provider'),
    ('accepted', 'Accepted'),
    ('rejected', 'Rejected'),
    ('cancelled', 'Cancelled'),
])
```
**Pattern**: Progressive state flow with clear transitions

#### Tracking and Audit
- `tracking=True` on critical fields
- Timestamp fields for operations (`signature_timestamp`, `last_retry_date`)
- Counter fields (`retry_count`, `usage_count`)
- User/message fields for debugging (`validation_errors`, `provider_response`)

### 3. Method Patterns

#### Action Methods
```python
def action_validate(self):
def action_sign(self):
def action_send_to_provider(self):
def action_retry(self):
def action_cancel(self):
```
**Pattern**: `action_` prefix for user-triggered operations, return notification dictionaries

#### Validation Methods
```python
def _validate_document(self):
def validate_for_edi(self, country_code=None):
def _check_move_compatibility(self, move):
```
**Pattern**: Return tuple `(is_valid, message)` or list of errors

#### Abstract Methods
```python
@abstractmethod
def send_document(self, document):
```
**Pattern**: Define interface in base, implement in specific providers

### 4. Error Handling Patterns

#### User-Friendly Errors
```python
raise UserError(_("No valid certificate found for signing"))
```

#### Validation Errors
```python
raise ValidationError(_("XML validation failed:\n%s") % '\n'.join(errors))
```

#### Error Tracking
- Store errors in fields for later review
- Use `blocking_level` to indicate severity
- Implement retry mechanisms with counters

### 5. Configuration Patterns

#### Company Scoping
```python
company_id = fields.Many2one(
    'res.company',
    required=True,
    default=lambda self: self.env.company
)
```

#### Default Provider Pattern
```python
is_default = fields.Boolean(string='Default Provider')

@api.constrains('is_default')
def _check_single_default(self):
    # Ensure only one default per company
```

### 6. Integration Patterns

#### Certificate Integration
- Extend existing `certificate.certificate` model
- Add EDI-specific fields without breaking original functionality
- Track usage for audit purposes

#### Provider Abstraction
```python
def make_request(self, method, endpoint, data=None, files=None):
    # Common HTTP request handling

def send_document(self, document):
    # To be overridden by specific providers
```

### 7. Computed Fields Pattern
```python
@api.depends('is_valid', 'date_end', 'edi_country_code')
def _compute_edi_validation_status(self):
```

## Recommendations

### 1. Complete Missing Files

Create the missing model files with consistent patterns:

#### edi_validator.py
```python
class EdiValidator(models.AbstractModel):
    _name = 'base.edi.validator'
    _description = 'EDI Validator'

    def validate_schema(self, content, schema):
        pass

    def validate_business_rules(self, document):
        pass
```

#### edi_workflow.py
```python
class EdiWorkflow(models.Model):
    _name = 'edi.workflow'
    _description = 'EDI Workflow'

    name = fields.Char(required=True)
    trigger = fields.Selection([...])
    action_ids = fields.One2many('edi.workflow.action', 'workflow_id')
```

### 2. Fix Import Issues

Update `models/__init__.py` to only import existing files:
```python
from . import edi_document
from . import edi_format
from . import edi_certificate
from . import edi_provider
# from . import edi_validator  # TODO: implement
# from . import edi_workflow  # TODO: implement
```

### 3. Create Security Files

#### ir.model.access.csv
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_edi_provider_user,edi.provider.user,model_edi_provider,base.group_user,1,0,0,0
access_edi_provider_manager,edi.provider.manager,model_edi_provider,account.group_account_manager,1,1,1,1
```

### 4. Create Basic Views

Start with minimal views to make the module installable:
```xml
<odoo>
    <record id="view_edi_provider_tree" model="ir.ui.view">
        <field name="name">edi.provider.tree</field>
        <field name="model">edi.provider</field>
        <field name="arch" type="xml">
            <tree>
                <field name="name"/>
                <field name="code"/>
                <field name="company_id"/>
            </tree>
        </field>
    </record>
</odoo>
```

### 5. Module Dependencies

Ensure all dependencies are correctly specified and available:
- `account_edi` ✓
- `certificate` ✓
- `account` ✓
- `base_setup` ✓

### 6. Consistency Improvements

1. **Naming Convention**: All EDI-specific models use `edi.` prefix
2. **Method Returns**: Standardize return types (dict for actions, tuple for validations)
3. **Error Messages**: Use translatable strings consistently with `_()`
4. **Logging**: Add consistent logging at INFO level for operations
5. **Documentation**: Add docstrings to all public methods

## Next Steps

1. **Priority 1**: Remove or comment out missing imports in `__init__.py`
2. **Priority 2**: Create minimal security and view files
3. **Priority 3**: Test module installation
4. **Priority 4**: Implement missing models based on patterns
5. **Priority 5**: Add comprehensive views and menus
6. **Priority 6**: Create demo data
7. **Priority 7**: Add unit tests

This modular approach ensures the module can be installed and tested incrementally while maintaining consistency with the established patterns.