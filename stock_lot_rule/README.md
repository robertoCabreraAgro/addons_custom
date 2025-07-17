# Stock Lot Rules

## Overview

The `stock_lot_rule` module is an advanced lot management system that automates lot nomenclature and date calculations in Odoo. It allows creating reusable rules to generate lot names and automatically calculate expiration, use, removal, and alert dates.

## Features

### Core Functionality

- **Automatic lot name generation** based on configurable patterns
- **Date extraction** from lot names using intelligent parsing
- **Automated date calculations** for expiration, use, removal, and alert dates
- **Format validation** to ensure consistency in lot naming
- **Change tracking** with mail.thread integration

### Pattern Configuration

The module supports flexible naming patterns using the following placeholders:

- `%(yy)s`: 2-digit year
- `%(yyyy)s`: 4-digit year  
- `%(mm)s`: 2-digit month
- `%(dd)s`: 2-digit day
- `%(product_code)s`: Product code
- `%(product_id)s`: Product ID
- `%(ref)s`: Vendor lot number

### Example Patterns

```python
# Basic patterns
"%(yy)s%(mm)s|%(product_id)s"           # → "2503|12345"
"%(yy)s%(mm)s%(dd)s|%(product_id)s"     # → "250315|12345"

# With vendor reference
"%(yy)s%(mm)s%(dd)s|%(product_id)s - %(ref)s"  # → "250315|12345 - AYE5AT009A"
```

## Installation

1. Copy the module to your Odoo addons directory
2. Update the module list in Odoo
3. Install the module from Apps menu

## Configuration

### Creating Lot Rules

1. Navigate to **Inventory > Configuration > Lot Rules**
2. Create a new rule with:
   - **Name**: Descriptive name for the rule
   - **Format Pattern**: Using available placeholders
   - **Date Calculations**: Days for expiration, use, removal, and alert dates

### Assigning Rules to Products

1. Go to **Inventory > Master Data > Products**
2. Select a product and edit
3. In the **Inventory** tab, set the **Lot Rule** field
4. The product will inherit the rule's date calculations

### Pre-configured Rules

The module includes three ready-to-use rules:

- **YYMM|PRODUCT_ID**: Basic year-month format
- **YYMMDD|PRODUCT_ID**: Full date format
- **YYMMDD|PRODUCT_ID - VENDOR_LOT_NUMBER**: With vendor reference

## Usage

### Lot Creation

When creating lots:

1. Start typing the lot name
2. The system will auto-complete based on the product's lot rule
3. Manufacturing date is extracted automatically
4. Expiration dates are calculated automatically
5. Validation ensures format compliance

### Smart Auto-completion

The system provides intelligent suggestions:

- **Partial input**: "2503" → "2503|12345" (if product ID is 12345)
- **Date validation**: Ensures realistic dates
- **Format checking**: Validates against the rule pattern

### Notifications

Users receive helpful notifications:

- ✅ **Valid format**: "Format valid: 250315|12345"
- ⚠️ **Placeholder warning**: "Requires vendor lot number"
- ❌ **Error**: "Invalid format. Expected: %(yy)s%(mm)s|%(product_id)s"

## Technical Details

### Models

#### `stock.lot.rule`
- Main configuration model for lot rules
- Handles pattern validation and date calculations
- Provides intelligent name generation methods

#### `stock.lot` (extended)
- Auto-computes manufacturing date from lot name
- Calculates expiration dates using lot rules
- Validates format compliance
- Provides auto-completion during input

#### `product.template` (extended)
- Links products to lot rules
- Inherits date calculations from rules
- Ensures consistency across lots

### Key Methods

#### Pattern Parsing
```python
def _get_manufacture_date(self, lot_name):
    """Extract manufacturing date from lot name"""
    
def _create_regex_from_pattern(self):
    """Create regex pattern from format pattern"""
```

#### Name Generation
```python
def _generate_lot_name(self, partial_name, product, ref_value=None):
    """Intelligent lot name generation"""
    
def _verify_lot_name_format(self, lot_name, product_id=None):
    """Validate lot name format"""
```

### Date Calculations

The system calculates dates based on manufacturing date:

- **Expiration Date**: Manufacturing date + expiration_time days
- **Use Date**: Manufacturing date + use_time days
- **Removal Date**: Manufacturing date + removal_time days
- **Alert Date**: Manufacturing date + alert_time days

## Business Benefits

### For Users
- **Automated nomenclature** reduces manual errors
- **Consistent formatting** across all lots
- **Intelligent suggestions** speed up data entry
- **Automatic date calculations** ensure compliance

### For Operations
- **Traceability** through structured lot naming
- **Inventory management** with automated alerts
- **Quality control** through date validation
- **Compliance** with industry standards

## Dependencies

- `stock`: Base inventory functionality
- `product_expiry`: Expiration date management
- `mail`: Notifications and tracking

## Compatibility

- **Odoo Version**: 18.0 (saas-18.2)
- **Python Version**: 3.11+
- **Database**: PostgreSQL

## Security

The module includes proper access controls:
- Read/write permissions for inventory managers
- Validation prevents malicious input
- Secure pattern parsing with regex

## Support

For issues or questions:
- Check the module's issue tracker
- Review the code documentation
- Contact the development team

## License

This module is licensed under OPL-1 (Odoo Proprietary License).

## Credits

**Author**: Agro Marin  
**Website**: https://www.agromarin.mx  
**Version**: saas~18.2.0.0.1