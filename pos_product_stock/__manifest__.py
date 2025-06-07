{
    "name": "POS Product Stock",
    "version": "saas~18.2.0.0.1",
    "category": "Point Of Sale",
    "summary": "Quantity of  all Products in each Warehouse",
    "description": "Shows Stock quantity in POS  for all Products in each Warehouse, Odoo 18",
    "author": "German Loredo",
    "maintainer": "German Loredo",
    "depends": ["base", "point_of_sale", "stock"],
    "data": [
        "views/res_cofig_settings_views.xml",
        "views/product_template_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_product_stock/static/src/xml/product_item.xml",
            "pos_product_stock/static/src/css/product_quantity.scss",
            "pos_product_stock/static/src/js/pos_location.js",
            "pos_product_stock/static/src/js/pos_payment_screen.js",
            "pos_product_stock/static/src/js/pos_session.js",
            "pos_product_stock/static/src/js/deny_order.js",
        ],
    },
    "images": ["static/description/banner.jpg"],
    "license": "AGPL-3",
    "installable": True,
    "auto_install": False,
    "application": False,
}
