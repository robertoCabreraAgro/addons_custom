{
    "name": "Product Abc Classification",
    "summary": """
        ABC classification for sales and warehouse management""",
    "version": "saas~18.4.0.0.1",
    "license": "AGPL-3",
    "author": "ACSONE SA/NV, ForgeFlow, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/product-attribute",
    "depends": ["product", "stock"],
    "data": [
        "views/abc_classification_product_level.xml",
        "views/abc_classification_profile.xml",
        "views/product_template.xml",
        "views/product_product.xml",
        "views/product_category.xml",
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
    ],
    "application": False,
    "installable": True,
}
