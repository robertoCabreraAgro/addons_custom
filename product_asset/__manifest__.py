{
    "name": "Product asset",
    "summary": "Manage assets",
    "version": "saas~18.2.1.0.0",
    "category": "Uncategorized",
    "author": "Odoo Community Association (OCA)",
    "depends": ["product_manufacturer", "hr"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/res_partner_data.xml",
        "data/product_category_data.xml",
        # "data/ir_cron_data.xml",
        "views/product_model_views.xml",
        "views/product_template_views.xml",
        "views/product_fleet_menuitem.xml",
    ],
    # "assets": {
    #     "web.assets_backend": [
    #         "date_range/static/src/js/*",
    #     ],
    # },
    "license": "LGPL-3",
    "installable": True,
}
