{
    "name": "Date Range",
    "summary": "Manage all kind of date range",
    "version": "19.0.0.0.1",
    "category": "Uncategorized",
    "website": "https://github.com/OCA/server-ux",
    "author": "ACSONE SA/NV, Odoo Community Association (OCA)",
    "license": "LGPL-3",
    "installable": True,
    "depends": ["web", "resource"],
    "data": [
        "security/ir.model.access.csv",
        "security/date_range_security.xml",
        "data/ir_cron_data.xml",
        "views/date_range_type_views.xml",
        "views/date_range_views.xml",
        "wizard/date_range_generator.xml",
        "views/date_range_menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "date_range/static/src/js/*",
        ],
    },
    "development_status": "Mature",
    "maintainers": ["lmignon"],
}
