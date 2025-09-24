{
    "name": "Documents - Asset Link",
    "version": "19.0.1.0.0",
    "category": "Productivity/Documents",
    "summary": "Link documents to assets via serial/lot numbers",
    "description": """
Asset Document Linking System
==============================

This module provides seamless integration between documents and assets by:

Core Features:
--------------
- Automatic linking of documents to assets via serial/lot numbers
- Asset-based document organization with dedicated folders per asset type
- Integration with stock.lot for tracking serialized assets
- Auto-categorization of documents based on asset type

Asset Organization:
------------------
- Separate folders for different asset types (Vehicles, Machinery, Properties, IT)
- Automatic folder assignment based on asset type
- Tags for asset categorization
- Asset-specific document views and filters

Integration:
-----------
- Links documents to product.template assets
- Tracks documents through stock.lot serial numbers
- Maintains relationship between documents and physical assets
- Works seamlessly with documents_compliance for expiration tracking
    """,
    "website": "",
    "depends": [
        "documents_compliance",
        "documents_product",
        "product_asset",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/documents_folder_data.xml",
        "data/documents_tag_data.xml",
        "data/ir_actions_server_data.xml",
        "data/res_company_data.xml",
        "views/documents_document_views.xml",
        "views/stock_lot_views.xml",
        "report/asset_compliance_report_views.xml",
        "wizard/res_config_settings_views.xml",
    ],
    "installable": True,
    "auto_install": True,
    "license": "OEEL-1",
    "post_init_hook": "_documents_product_asset_post_init",
}
