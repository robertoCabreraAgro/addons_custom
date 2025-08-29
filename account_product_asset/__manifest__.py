{
    "name": "Accounting/Product Asset bridge",
    "category": "Accounting/Accounting",
    "summary": "Manage accounting with product assets",
    "version": "1.1",
    "author": "AgroMarin",
    "depends": ["product_asset", "account"],
    "data": [
        "views/account_move_views.xml",
        "views/stock_lot_views.xml",
        "views/product_asset_log_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
    "post_init_hook": "post_init_hook",
}
