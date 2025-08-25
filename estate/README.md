# Real Estate Module for Odoo 18

A comprehensive real estate management module built for Odoo 18. This module allows you to manage properties, offers, customers, and generate detailed reports.

## Features

- **Property Management**: Create and manage real estate properties with detailed information
- **Offer System**: Handle property offers with validation rules and status tracking
- **Customer Management**: Track customer offers and interactions
- **Dashboard**: Visual dashboard with statistics and charts
- **Reporting**: Generate PDF reports for properties
- **Security**: Role-based access control (Manager/User)
- **Wizards**: Bulk operations for creating multiple offers

## Installation

1. Place the `estate` folder in your Odoo addons directory
2. Update the apps list in Odoo
3. Install the "Real Estate" module

## Models

### Estate Property
Main model for property listings with fields for:
- Basic information (name, description, postcode)
- Pricing (expected price, selling price)
- Features (bedrooms, living area, garden, garage)
- Status management (new, offer received, offer accepted, sold, canceled)

### Estate Property Type
Categorize properties by type with sequencing support

### Estate Property Tag
Tagging system for properties with color coding

### Estate Property Offer
Offer management system with:
- Price validation (min. 90% of expected price)
- Validity periods and deadlines
- Status tracking (accepted/refused)

## Security

Two user groups:
- **Estate User**: Can manage their own properties and offers
- **Estate Manager**: Full access to all properties and configuration

## Usage

1. **Create Property Types** and **Tags** in Configuration menu
2. **Add Properties** with detailed information
3. **Manage Offers** from property form or dedicated menu
4. **Use Dashboard** for overview and statistics
5. **Generate Reports** for individual properties

## Technical Details

- Built with Odoo 18 framework
- Uses Python constraints and SQL constraints
- Implements computed fields and onchange methods
- Includes QWeb reports and dashboard views
- Follows Odoo development best practices

## Dependencies

- base
- web

## License

LGPL-3