{
    "name": "Product manufacturer",
    "version": "saas~18.4.0.0.1",
    "summary": "Adds manufacturers and attributes on the product view.",
    "website": "https://github.com/OCA/product-attribute",
    "author": "Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "category": "Product",
    "depends": ["product"],
    "data": [
        "views/res_partner_views.xml",
        "views/product_product_views.xml",
        "views/product_template_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}
