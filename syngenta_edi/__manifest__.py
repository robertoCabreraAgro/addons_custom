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
        "product_manufacturer",
    ],
    "data": [
        # Security
        "security/security.xml",
        "security/ir.model.access.csv",
        # Data
        "data/ir_sequence_data.xml",
        "data/res_partner_data.xml",
        # Views
        "views/res_company_views.xml",
        "views/syngenta_commercial_agreement_views.xml",
        "views/syngenta_sale_report_views.xml",
        "views/syngenta_sale_report_line_views.xml",
        "views/syngenta_stock_report_views.xml",
        "views/syngenta_stock_report_line_views.xml",
        "views/menuitem_views.xml",
    ],
    "pre_init_hook": "_pre_init_hook",
    "installable": True,
    "auto_install": False,
    "application": False,
}
