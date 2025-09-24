{
    "name": "Documents Compliance",
    "summary": "Document compliance management with expiration tracking",
    "description": """
Document Compliance Management System
======================================

This module provides comprehensive document compliance management with:

Core Features:
--------------
- Document type categorization and configuration
- Compliance status tracking and monitoring
- Document expiration management
- Multi-level notification system (30, 7, 1 day warnings)
- Document renewal workflows
- Verification and approval tracking

Compliance Management:
---------------------
- Define mandatory vs optional document types
- Track compliance percentage per entity
- Monitor missing, expired, and expiring documents
- Automated compliance reporting
- Document verification workflows

Document Types:
--------------
- Configurable document categories
- Default validity periods
- Renewal requirements
- Template attachments
- Instructions for obtaining/renewing documents

Notifications:
-------------
- Configurable notification periods
- Multiple recipient management
- Activity-based reminders
- Email notifications for critical documents

Integration:
-----------
- Seamless integration with Odoo Documents module
- Support for document tags and folders
- Activity tracking via mail module
    """,
    "author": "Luis Marin",
    "website": "https://agromarin.mx",
    "category": "Productivity/Documents",
    "version": "19.0.2.0.0",
    "depends": ["documents", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/data.xml",
        "data/ir_cron_data.xml",
        "views/document_type_views.xml",
        "views/documents_document_views.xml",
        "report/document_compliance_report_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "OPL-1",
}
