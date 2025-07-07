# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Table of Contents

1. [Overview](#overview)
2. [Technology Stack](#technology-stack)
   - [Core Platform](#core-platform)
   - [Key Dependencies](#key-dependencies)
   - [External Documentation](#external-documentation)
3. [Project Architecture](#project-architecture)
   - [Repository Structure](#repository-structure)
   - [Module Categories](#module-categories)
   - [Module Structure](#module-structure)
4. [Development Commands](#development-commands)
   - [Module Management](#module-management)
   - [Testing and Debugging](#testing-and-debugging)
   - [Migration and Maintenance](#migration-and-maintenance)
5. [Coding Standards](#coding-standards)
   - [AgroMarin Development Standards](#agromarin-development-standards)
   - [Odoo 18.0 Specific Conventions](#odoo-180-specific-conventions)
   - [OCA Guidelines Applied](#oca-guidelines-applied)
6. [Code Examples](#code-examples)
   - [Basic Module Structure](#basic-module-structure)
   - [Migration Pattern Example](#migration-pattern-example)
7. [Business Context](#business-context)
   - [Mexican Localization Focus](#mexican-localization-focus)
   - [Agricultural Domain](#agricultural-domain)
8. [Task Management and Branching](#task-management-and-branching)
   - [Task ID Requirements](#task-id-requirements)
   - [Branch Naming Convention](#branch-naming-convention)
9. [Working with this Repository](#working-with-this-repository)

## Overview

This is an Odoo addons repository containing custom modules for the Agromarin ERP system. The repository contains 40+ Odoo addons for various business functions including accounting, HR, inventory, manufacturing, and Mexican localization.

## Technology Stack

### Core Platform
- **Odoo Version**: 18.0 (saas-18.2 branch)
- **Python Version**: 3.11+
- **Database**: PostgreSQL with PostGIS extension

### Key Dependencies
- **Python**: shapely, geojson, pyproj (geospatial), requests, lxml
- **JavaScript**: No external frameworks (native Odoo web framework)
- **Development Tools**: 
  - Linters: pylint, eslint
  - Formatters: black, prettier
  - Testing: Odoo's built-in testing framework

### External Documentation
- [Odoo 18.0 Developer Documentation](https://www.odoo.com/documentation/18.0/developer.html)
- [Claude Code Documentation](https://docs.anthropic.com/claude/docs/claude-code)
- [OCA Guidelines](https://github.com/OCA/odoo-community.org/blob/master/website/Contribution/CONTRIBUTING.rst)

## Project Architecture

### Repository Structure
```
agromarin-addons/
├── marin/                   # Main application module (meta-module)
├── marin_data/              # Data module for main application
├── account_*/               # Accounting & Finance modules
├── hr_*/                    # HR & Payroll modules
├── stock_*/                 # Inventory & Manufacturing modules
├── l10n_mx_*/               # Mexican localization modules
├── base_*/                  # Infrastructure modules
├── documents_*/             # Document management
├── gps_tracking/            # GPS tracking functionality
├── base_geoengine/          # Geospatial core functionality
└── planning/                # Task planning documents
```

### Module Categories

**Accounting & Finance:**
- `account_invoice_margin*`: Invoice margin calculations
- `account_move_*`: Journal entry operations and templates
- `l10n_mx_*`: Mexican localization (EDI, payroll, fiscal regime)

**HR & Payroll:**
- `hr_*`: Employee management, payroll, attendance
- `l10n_mx_edi_payslip`: Mexican payroll with EDI compliance
- `hr_employee_*`: Employee name handling and personal data

**Inventory & Manufacturing:**
- `stock_*`: Inventory management and location handling
- `product_*`: Product management and manufacturing
- `gps_tracking`: GPS tracking for fleet/inventory

**Geospatial:**
- `base_geoengine`: Core geospatial functionality using PostGIS
- `base_geoengine_demo`: Demo data for geospatial features

**Infrastructure:**
- `base_*`: Core extensions and approval workflows
- `date_range`: Date range management
- `documents_*`: Document management with expiry tracking

### Module Structure
Each addon follows standard Odoo structure:
```
addon_name/
├── __manifest__.py          # Module definition
├── __init__.py             # Module initialization
├── models/                 # Data models
├── views/                  # XML views
├── security/               # Access rights and rules
├── data/                   # Configuration data
├── static/                 # Assets (JS, CSS, images)
├── tests/                  # Unit tests
└── i18n/                   # Translations
```

## Development Commands

### Module Management
```bash
# Install module
./odoo-bin -u module_name -d database_name

# Update module
./odoo-bin -u module_name -d database_name

# Create new module scaffold
./odoo-bin scaffold module_name /path/to/addons

# Install all modules in path
./odoo-bin -u all -d database_name --addons-path=/path/to/addons
```

### Testing and Debugging
```bash
# Run tests for specific module
./odoo-bin -u module_name -d database_name --test-enable

# Run tests with coverage
./odoo-bin -u module_name -d database_name --test-enable --log-level=test

# Debug mode
./odoo-bin -d database_name --dev=all

# Shell access
./odoo-bin shell -d database_name
```

### Migration and Maintenance
```bash
# Update module list
./odoo-bin -u base -d database_name --stop-after-init

# Migrate data
./odoo-bin -u module_name -d database_name --stop-after-init

# Check module dependencies
./odoo-bin -u module_name -d database_name --test-enable --stop-after-init
```

## Coding Standards

### AgroMarin Development Standards

**Language Requirements:**
- **English Only**: All code, comments, docstrings, and variable names must be in English
- **Mandatory Docstrings**: Every method and class must have comprehensive docstrings
- **Agricultural Domain**: Consider agricultural business logic and terminology when naming

**Code Quality:**
- Follow PEP 8 standards for Python code
- Use meaningful variable and method names
- Add type hints where applicable
- Input validation and sanitization for all user inputs

### Odoo 18.0 Specific Conventions

**XML Views:**
- Use `<list>` instead of `<tree>` for list views
- Simplify chatter to `<chatter />` (no additional attributes needed)
- New expression syntax for dynamic attributes:
  ```xml
  <!-- Old way -->
  <field name="field_name" attrs="{'invisible': [('state', '=', 'draft')]}"/>
  
  <!-- Odoo 18.0 way -->
  <field name="field_name" invisible="state == 'draft'"/>
  ```

**Python Models:**
- Replace `name_get()` with `_compute_display_name()` method
- Use `@api.depends_context` for context-dependent computations
- New `_rec_names_search()` method for custom search behavior

**JavaScript/XML:**
- Remove `/** @odoo-module **/` headers (automatically handled)
- Remove `owl="1"` attributes from XML templates
- Use native Odoo web framework patterns

### OCA Guidelines Applied

This repository follows the **OCA (Odoo Community Association) coding guidelines**:

1. **Python Code Style:**
   - Follow PEP 8 standards
   - Use meaningful variable and method names
   - Add proper docstrings to all methods and classes
   - Use type hints where applicable

2. **Module Structure:**
   - Standard Odoo module directory structure
   - Proper separation of concerns (models, views, security, data)
   - Clear and descriptive file naming

3. **Commit Messages:**
   - Use conventional format: `[TAG] module: description`
   - Tags: IMP (improvement), FIX (bug fix), ADD (new feature), REF (refactor)
   - Write messages in English
   - Keep messages concise but descriptive
   - Maximum 80 characters per line

4. **XML Views:**
   - Use semantic field grouping
   - Include proper help text and labels
   - Follow Odoo UI/UX guidelines

5. **Security:**
   - Proper access rights configuration
   - Input validation and sanitization
   - Follow security best practices

6. **Testing:**
   - Write unit tests for business logic
   - Include integration tests for complex workflows
   - Test edge cases and error conditions

7. **Documentation:**
   - Clear module descriptions in `__manifest__.py`
   - Comprehensive README files where needed
   - Code comments for complex business logic

## Code Examples

### Basic Module Structure

**__manifest__.py Example:**
```python
{
    'name': 'AgroMarin Custom Module',
    'version': '18.0.1.0.0',
    'category': 'Agriculture',
    'summary': 'Custom agricultural functionality',
    'author': 'AgroMarin',
    'depends': ['base', 'stock', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/custom_views.xml',
        'data/custom_data.xml',
    ],
    'installable': True,
    'auto_install': False,
}
```

**Model Example:**
```python
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class AgriculturalProduct(models.Model):
    """Agricultural product management for farming operations."""
    
    _name = 'agricultural.product'
    _description = 'Agricultural Product'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Product Name', required=True, tracking=True)
    crop_type = fields.Selection([
        ('grain', 'Grain'),
        ('vegetable', 'Vegetable'),
        ('fruit', 'Fruit'),
    ], string='Crop Type', required=True)
    harvest_date = fields.Date(string='Expected Harvest Date')
    
    @api.depends('name', 'crop_type')
    def _compute_display_name(self):
        """Compute display name combining name and crop type."""
        for record in self:
            record.display_name = f"{record.name} ({record.crop_type})"
    
    @api.constrains('harvest_date')
    def _check_harvest_date(self):
        """Validate harvest date is not in the past."""
        for record in self:
            if record.harvest_date and record.harvest_date < fields.Date.today():
                raise ValidationError("Harvest date cannot be in the past.")
```

**View Example (Odoo 18.0):**
```xml
<odoo>
    <record id="view_agricultural_product_form" model="ir.ui.view">
        <field name="name">agricultural.product.form</field>
        <field name="model">agricultural.product</field>
        <field name="arch" type="xml">
            <form string="Agricultural Product">
                <sheet>
                    <group>
                        <field name="name"/>
                        <field name="crop_type"/>
                        <field name="harvest_date" invisible="crop_type == 'grain'"/>
                    </group>
                </sheet>
                <chatter />
            </form>
        </field>
    </record>

    <record id="view_agricultural_product_list" model="ir.ui.view">
        <field name="name">agricultural.product.list</field>
        <field name="model">agricultural.product</field>
        <field name="arch" type="xml">
            <list string="Agricultural Products">
                <field name="name"/>
                <field name="crop_type"/>
                <field name="harvest_date"/>
            </list>
        </field>
    </record>
</odoo>
```

**Test Example:**
```python
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError

class TestAgriculturalProduct(TransactionCase):
    """Test agricultural product functionality."""
    
    def setUp(self):
        """Set up test data."""
        super().setUp()
        self.ProductModel = self.env['agricultural.product']
    
    def test_create_agricultural_product(self):
        """Test creating an agricultural product."""
        product = self.ProductModel.create({
            'name': 'Test Corn',
            'crop_type': 'grain',
            'harvest_date': '2024-09-15',
        })
        self.assertEqual(product.name, 'Test Corn')
        self.assertEqual(product.crop_type, 'grain')
    
    def test_harvest_date_validation(self):
        """Test harvest date validation."""
        with self.assertRaises(ValidationError):
            self.ProductModel.create({
                'name': 'Test Corn',
                'crop_type': 'grain',
                'harvest_date': '2020-01-01',  # Past date
            })
```

### Migration Pattern Example
```python
def migrate(cr, version):
    """Migrate data from old structure to new structure."""
    if not version:
        return
    
    # Update field names
    cr.execute("""
        UPDATE agricultural_product 
        SET new_field_name = old_field_name 
        WHERE old_field_name IS NOT NULL
    """)
    
    # Add new required fields with default values
    cr.execute("""
        UPDATE agricultural_product 
        SET crop_type = 'grain' 
        WHERE crop_type IS NULL
    """)
```

## Business Context

### Mexican Localization Focus
This repository heavily focuses on Mexican business requirements:
- **EDI Compliance**: Electronic Document Interchange for tax authorities
- **CFDI Generation**: Mexican tax receipt (Comprobante Fiscal Digital) generation
- **Payroll Integration**: Mexican tax calculations and payroll processing
- **Partner Blocklist**: Management of blocked business partners
- **Fiscal Regime**: Mexican fiscal regime handling

### Agricultural Domain
- **Crop Management**: Tracking of agricultural products and harvest cycles
- **Inventory Tracking**: Location-based inventory for agricultural products
- **GPS Integration**: Geospatial tracking for fleet and field operations
- **Seasonal Planning**: Date range management for agricultural seasons

## Task Management and Branching

### Task ID Requirements
When collaborating on this repository, **every task must have a valid Task ID**:

- **Task Context**: Task planning documents are stored in `/planning/` directory
- **Task ID Extraction**: The Task ID is extracted from the filename (e.g., `9169.md` → Task ID: `9169`)
- **Mandatory for Claude Code**: Claude Code must always request or extract the Task ID before starting work
- **Planning Documentation**: Each task should have a corresponding `.md` file in `/planning/` with detailed requirements

### Branch Naming Convention
Use the following format for all feature branches:
```
<ODOO_VERSION>-T<TASK_ID>-<GITHUB_USERNAME>
```

**Examples:**
- Task 9169, Odoo 18.2, user suniagajose: `18.2-t9169-suniagajose`
- Task 9136, Odoo 18.2, user johndoe: `18.2-t9136-johndoe`

**Why Task IDs are Important:**
- Enables traceability between code changes and business requirements
- Facilitates project management and progress tracking
- Ensures proper documentation and context for each feature
- Maintains consistency across team collaboration
- Links development work to specific planning documents

## Working with this Repository

1. Each module is self-contained but may depend on others
2. The `marin` module provides the complete application setup
3. Test individual modules using Odoo's module testing framework
4. Check `__manifest__.py` for module-specific dependencies
5. Many modules include demo data for testing purposes
6. Use the `/planning/` directory for task documentation and requirements
7. Follow the branch naming convention for all feature work
8. Always include comprehensive docstrings and tests for new functionality