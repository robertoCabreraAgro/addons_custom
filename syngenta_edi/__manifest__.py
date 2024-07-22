{
    "name": "Syngenta EDI",
    "summary": """
    Module required to send reports to the Syngenta's web service.
    """,
    "author": "Vauxoo",
    "website": "https://www.vauxoo.com",
    "license": "OPL-1",
    "category": "Installer",
    "version": "1.0",
    "depends": [
        "sale_stock",
    ],
    "data": [
        # Security
        "security/security.xml",
        "security/ir.model.access.csv",
        # Data
        "data/ir_sequence_data.xml",
        "data/res_partner_data.xml",
        # Views
        "views/product_product_views.xml",
        "views/product_template_views.xml",
        "views/res_company_views.xml",
        "views/syngenta_sale_agreement_views.xml",
        "views/syngenta_sale_document_views.xml",
        "views/syngenta_sale_line_views.xml",
        "views/syngenta_stock_document_views.xml",
        "views/syngenta_stock_quant_views.xml",
        "views/menuitem_views.xml",
    ],
    "pre_init_hook": "_pre_init_hook",
    "installable": True,
    "auto_install": False,
    "application": False,
}
