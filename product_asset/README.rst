==============
Product Asset
==============

This module transforms Odoo's inventory management system into a comprehensive asset management platform. It extends the standard product and lot/serial number functionality to enable detailed tracking and management of individual assets such as vehicles, machinery, equipment, and properties.

**Table of contents**

.. contents::
   :local:

Description
===========

The Product Asset module provides the following capabilities:

* **Asset Classification**: Define products as specific asset types (Vehicle, Machinery, Equipment, etc.)
* **Individual Asset Tracking**: Each serial number becomes a detailed asset record with comprehensive information
* **Detailed Asset Profiles**: Track identification details (license plates, VIN, chassis numbers), technical specifications, and financial information
* **Personnel Assignment**: Assign operators (e.g., drivers) and asset managers with full assignment history
* **Comprehensive Logging System**: Record all asset-related activities including:
  
  * Services and maintenance
  * Fuel purchases and consumption
  * Insurance policies and contracts
  * Toll charges and other expenses
  * Operator changes and assignments

* **Automated Features**:
  
  * Odometer tracking with automatic calculation from service logs
  * Contract renewal reminders for insurance and leases
  * Budget tracking for fuel cards and highway tolls
  * Activity state management for due dates

* **Vehicle Fleet Focus**: While flexible for any asset type, includes specialized features for vehicle management including fuel efficiency, CO2 emissions, and tank capacity

Installation
============

To install this module:

1. Place the module in your Odoo addons path
2. Update the module list (Apps menu > Update Apps List)
3. Search for "Product Asset" and install

The module depends on:

* ``stock`` - For lot/serial number management
* ``hr`` - For employee/operator assignment
* ``product_manufacturer`` - For manufacturer tracking
* ``uom_extended`` - For extended units of measure

Configuration
=============

Product Configuration
---------------------

1. Navigate to **Inventory > Products > Products**
2. Create or edit a product that will be managed as an asset
3. In the **Inventory** tab:
   
   * Set **Tracking** to "By Unique Serial Number"

4. In the **Asset** tab:
   
   * Set **Asset Type** (Vehicle, Equipment, Machinery, etc.)
   * Configure default technical specifications:
     
     * Power (HP)
     * CO2 emissions
     * Fuel consumption (if applicable)
     * Tank capacity (if applicable)

Service Products
----------------

The module creates default service products for logging activities:

* Fuel
* Repairs
* Insurance
* Tolls
* Other services

You can create additional service products as needed for categorizing asset logs.

Usage
=====

Creating Assets
---------------

1. When receiving products configured as assets, the system will require serial numbers
2. Each serial number automatically becomes an asset record
3. Navigate to **Assets > Assets** to view all assets

Managing Individual Assets
--------------------------

From the asset form view, you can:

1. **Basic Information**:
   
   * Set license plate (for vehicles)
   * Enter VIN/Chassis number
   * Specify acquisition date and values

2. **Assignments**:
   
   * Assign an operator (employee who uses the asset)
   * Assign an asset manager (responsible for maintenance)
   * View assignment history

3. **Financial Data**:
   
   * Original value
   * Current/residual value
   * Budget allocations

4. **Activity Logging**:
   
   Click "Log Service" to record:
   
   * Maintenance and repairs
   * Fuel purchases
   * Insurance renewals
   * Any other asset-related expense

Tracking and Reports
--------------------

The module provides several smart buttons for quick access to:

* **Services**: All maintenance and service records
* **Contracts**: Active and expired contracts (insurance, leases)
* **Fuel**: Fuel purchase history and consumption tracking
* **Costs**: Complete cost analysis by category

Contract Management
-------------------

For contracts like insurance:

1. Click "Log Service" and select an insurance product
2. Set start and end dates
3. The system will automatically:
   
   * Track contract status (active/expired)
   * Generate activities for renewal reminders
   * Calculate days until expiration

Budget Management
-----------------

For fuel cards and toll accounts:

1. Set budget amounts in the asset form
2. Log expenses against these budgets
3. View current balance and reload requirements

Known issues / Roadmap
======================

* Extend reporting capabilities with graphical dashboards
* Add preventive maintenance scheduling
* Implement asset depreciation calculations
* Create mobile app interface for field operators
* Add GPS tracking integration
* Develop asset utilization analytics
