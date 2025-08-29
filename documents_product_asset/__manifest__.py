{
    "name": "Documents - Product Asset",
    "version": "1.0",
    "category": "Productivity/Documents",
    "summary": "Asset documents management",
    "description": """
        Adds asset data to documents
    """,
    "website": "",
    "depends": ["documents_product", "product_asset"],
    "data": [
        "data/documents_folder_data.xml",
        "data/documents_tag_data.xml",
        "data/ir_actions_server_data.xml",
        "data/res_company_data.xml",
        "views/stock_lot_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "auto_install": True,
    "license": "OEEL-1",
    "post_init_hook": "_documents_product_asset_post_init",
}
