
{
    "name": "Approval - Account",
    "version": "1.0",
    "category": "Human Resources/Approvals",
    "description": """
        This module adds to the approvals workflow the possibility to generate
        Journal entries from an approval request.
    """,
    "depends": ["approvals", "account"],
    "data": [
        "data/approval_category_data.xml",
        "views/approval_request_views.xml",
        "views/account_move_views.xml",
    ],
    "installable": True,
    "auto_install": True,
    "license": "OEEL-1",
}
