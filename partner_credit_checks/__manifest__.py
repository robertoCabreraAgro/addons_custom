{
    "name": "Partner Credit Checks",
    "version": "1.0",
    "depends": ["base", "account", "sale", "documents"],
    "author": "Agro Marin",
    "category": "Finance",
    "summary": "Customer Credit Evaluation and Management",
    "description": """
Manage Customer Credit
======================

This module provides a complete solution for managing customer credits:

* Automating credit status evaluation
* Enforcing document compliance
* Integrating with sales and invoicing workflows

Key Features:
-------------
* Four-tier credit status system (Cash Only, Under Review, Approved, Legal Process)
* Configurable credit dossier types with custom rules
* Document expiration tracking
* Payment history analysis
* Automated daily status updates
* Sales order validation
* Customer invoices validation
* Legal process lockdown
* Comprehensive reporting
    """,
    "data": [
        # Security definitions
        "security/res_groups_security.xml",
        "security/ir.model.access.csv",
        # Data files
        "data/documents_tag_data.xml",
        "data/res_partner_dossier_data.xml",
        # View definitions
        "views/res_partner_dossier_views.xml",
        "views/res_partner_views.xml",
        # Menu definitios
        "views/partner_credit_status_menus.xml",  # Last because referencing actions defined in previous files
    ],
    "installable": True,
    "application": False,
}
