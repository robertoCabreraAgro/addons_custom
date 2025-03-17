
{
    "name": "Approvals - Purchase - Stock",
    "version": "1.0",
    "category": "Human Resources/Approvals",
    "description": """ Technical module to link Approvals, Purchase and Inventory together. """,
    "depends": ["approval_purchase", "purchase_stock"],
    "data": [
        "views/approval_product_line_views.xml",
        "views/approval_request_views.xml",
    ],
    "installable": True,
    "auto_install": True,
    "license": "OEEL-1",
}
