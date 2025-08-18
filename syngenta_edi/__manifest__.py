{
    "name": "Syngenta EDI",
    "summary": """
    Module required to send reports to the Syngenta's web service.
    """,
    "author": "Vauxoo",
    "website": "https://www.vauxoo.com",
    "license": "OPL-1",
    "category": "Installer",
    "version": "saas~18.4.0.0.1",
    "depends": [
        "product_manufacturer",
    ],
    "data": [
        "security/res_group_data.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence_data.xml",
        "views/res_company_views.xml",
        "views/syngenta_commercial_agreement_views.xml",
        "views/syngenta_sale_report_views.xml",
        "views/syngenta_sale_report_line_views.xml",
        "views/syngenta_stock_report_views.xml",
        "views/syngenta_stock_report_line_views.xml",
        "views/menuitem_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
