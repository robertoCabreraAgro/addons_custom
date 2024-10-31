
{
    "name": "Account Invoice Margin",
    "summary": "Show margin in invoices",
    "version": "18.0.1.0.0",
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
        "views/account_invoice_margin_view.xml",
    ],
    "pre_init_hook": "pre_init_hook",
}
