# Mexico - Multiple Fiscal Regimes

## Overview

This module extends the Mexican localization (l10n_mx_edi) to support multiple fiscal regimes per partner, allowing dynamic selection of fiscal regime in invoices according to SAT requirements. It replaces the original selection field with a new model-based approach for better management and flexibility.

## Features

### New Fiscal Regime Model
- **l10n_mx_edi.fiscal.regime**: New model to manage fiscal regimes as independent records
- **Pre-loaded Data**: All official SAT fiscal regimes are automatically created
- **Management Interface**: Dedicated views to manage fiscal regimes
- **Code Uniqueness**: Ensures fiscal regime codes are unique across the system

### Partner Enhancements
- **Multiple Fiscal Regimes**: Partners can now have multiple allowed fiscal regimes
- **Default Fiscal Regime**: Set a default regime from the allowed regimes list using Many2one field
- **Domain Constraints**: Default regime is automatically constrained to allowed regimes
- **Automatic Validation**: Ensures data consistency with proper constraints
- **Backward Compatibility**: Computed field maintains compatibility with existing code

### Invoice Enhancements
- **Dynamic Fiscal Regime Selection**: Select specific fiscal regime per invoice
- **Auto-population**: Invoice fiscal regime auto-populates from partner's default
- **Proper Domain**: Invoice regime selection limited to partner's allowed regimes
- **Sales Journal Only**: Field only visible for sales journals
- **CFDI Integration**: Selected regime is properly used in CFDI generation

### CFDI Integration
- **Enhanced Document Processing**: EDI documents now use the new fiscal regime model
- **Priority System**: Invoice-specific regime takes priority over partner default
- **Fallback Mechanism**: Graceful fallback to partner regime and then default
- **Backward Compatibility**: Supports legacy selection field during migration
