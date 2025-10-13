{
    "name": "Base Approval Sales",
    "version": "saas~18.2.3.0.2",
    "category": "Sales/Sales",
    "sequence": 95,
    "summary": "Centralized approval workflow for sales orders",
    "depends": [
        "sale",
        "base_approval",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/approval_category_data.xml",
        "views/sale_order_views.xml",
        "views/approval_request_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "base_approval_sales/static/src/css/approval_styles.css",
        ],
    },
    "demo": [],
    "application": False,
    "installable": True,
    "auto_install": False,
    "license": "OEEL-1",
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
}