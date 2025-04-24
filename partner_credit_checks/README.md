

![Odoo Version](https://img.shields.io/badge/Odoo-15.0%2520%7C%252016.0-blue)  
![License](https://img.shields.io/badge/License-LGPL--3-lightgrey)

## Overview

The **Partner Credit Checks** module (formerly Partner Credit Status) enhances Odoo's partner management with comprehensive credit validation features, including credit limits, credit status tracking, and document compliance requirements.

## Key Features

### Automated Credit Status Management

- **Four-tier status system**:
    - `Cash Only`: No credit allowed or incomplete documentation
    - `Under Review`: Pending issues detected
    - `Credit Approved`: Fully compliant
    - `Legal Process`: Manually restricted

### Document Compliance Engine

- Configurable dossier types with custom rules
- Automatic validation of:
    - Document expiration dates
    - Required collateral amounts
    - Minimum/maximum document quantities
    - Payment history analysis

### Business Process Controls
- Sales order validation based on credit status
- Invoice blocking for non-compliant partners
- Legal process lockdown functionality

### Scheduled Automation
- Daily cron job for status reevaluation
- Automatic demotion for expired documents
- Smart promotion when compliance is restored

## Installation

1. Clone the repository into your Odoo addons directory
2. Restart your Odoo service
3. Update the Apps list (Developer Mode required)
4. Install the module

## Configuration

### Setting Up Credit Dossiers

Navigate to:  
`Contacts → Configuration → Credit Dossiers`

1. Create dossier types (e.g., "High Reliability", "Standard", "Restricted")
2. Define rules for each:
    - Required document types
    - Expiration policies
    - Collateral requirements
    - Quantity ranges

### Partner Setup
1. Open any company partner record
2. Assign appropriate dossier type
3. Upload required documents in the "Credit Documents" tab

## Usage

### Status Transitions

| Status          | Trigger Conditions                     | Business Impact                 |
| --------------- | -------------------------------------- | ------------------------------- |
| Cash Only       | No dossier assigned or rule violations | Cash payments only              |
| Under Review    | Expired docs or overdue invoices       | Credit suspended pending review |
| Credit Approved | All requirements met                   | Full credit privileges          |
| Legal Process   | Manual intervention                    | Complete account freeze         |

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss proposed changes.

## License

This module is licensed under LGPL-3 as all Odoo community modules.