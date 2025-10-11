{
    "name": "Base Approval Sales",
    "version": "saas~18.2.3.0.1",
    "category": "Sales/Sales",
    "sequence": 95,
    "summary": "Centralized approval workflow for sales orders",
    "description": """
        Sales Order Approval Integration
        ================================

        This module extends the sale order workflow with mandatory approval states
        integrated directly into the statusbar.

        Features:
        • Universal mandatory approval for ALL sales orders
        • Sales-only integration (no purchase dependencies)
        • Extended state field with pending_approval and approved states
        • Statusbar integration with approval workflow
        • Many2one relationship with approval.request
        • Smart button visibility using attrs syntax
        • Permission-based approval actions
        • Complete view integration (form, tree, kanban, search)

        Technical:
        • Clean architecture with minimal dependencies (sale + base_approval only)
        • Many2one direct relationship instead of string references
        • Compatible attrs syntax with | and & operators
        • Native widget integration without OWL dependencies
        • Extended statusbar with approval states integration
        • State-based workflow validation with proper transitions
    """,
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