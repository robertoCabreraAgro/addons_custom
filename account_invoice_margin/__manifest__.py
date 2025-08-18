{
    "name": "Account Invoice Margin",
    "summary": "Show margin in invoices",
    "version": "saas~18.4.0.0.1",
    "category": "Account",
    "website": "https://github.com/OCA/margin-analysis",
    "author": "Tecnativa, GRAP, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "development_status": "Production/Stable",
    "maintainers": ["sergio-teruel"],
    "application": False,
    "installable": True,
    "depends": ["account"],
    "data": [
        "security/res_groups_data.xml",
        "views/account_move_views.xml",
    ],
    "pre_init_hook": "pre_init_hook",
}
