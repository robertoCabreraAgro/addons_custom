{
    "name": "Work Teams",
    "version": "1.1",
    "category": "Sales/Sales",
    "summary": "Work Teams",
    "description": """
        Using this application you can manage Work Teams with CRM and/or Sales
        =======================================================================
    """,
    "website": "https://www.odoo.com/app/crm",
    "depends": ["base", "mail"],
    "data": [
        "security/sales_team_security.xml",
        "security/ir.model.access.csv",
        "data/crm_team_data.xml",
        "views/work_team_views.xml",
        "views/work_team_member_views.xml",
    ],
    "demo": [
        "data/crm_team_demo.xml",
    ],
    "installable": True,
    "assets": {
        "web.assets_backend": [
            "sales_team/static/**/*",
        ],
    },
    "license": "LGPL-3",
}
