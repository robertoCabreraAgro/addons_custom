{
    "name": "Base Approval Purchases",
    "version": "18.0.1.0.0",
    "category": "Purchase",
    "summary": "Purchase Order approval workflow management",
    "description": """
        This module extends base_approval to handle purchase order approvals specifically.
        It provides:
        - Purchase order approval requests
        - Product line management for purchase approvals
        - Purchase-specific approval categories
    """,
    "author": "AgroMarin",
    "website": "https://www.agromarin.com",
    "depends": [
        "base_approval",
        "purchase"
    ],
    "data": [
    ],
    "demo": [
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
    "license": "LGPL-3",
}