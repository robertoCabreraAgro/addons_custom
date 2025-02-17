# Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "Product manufacturer",
    "version": "saas~18.2.1.0.1",
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
    "auto_install": False,
    "installable": True,
}
