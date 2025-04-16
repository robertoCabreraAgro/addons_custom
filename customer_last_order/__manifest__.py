# -*- coding: utf-8 -*-
{
    "name": "Customer's last order",
    "summary": "Show the customer's last sale / POS date and reference",
    "author": "Javier Diez",
    "website": "https://javierdiez.netlify.app/",
    "license": "AGPL-3",
    "category": "Sale",
    "version": "1.0",
    # any module necessary for this one to work correctly
    "depends": ["base", "sale_management"],
    # always loaded
    "data": [
        "views/res_partner_views.xml",
    ],
    "images": ["static/images/banner.png", "static/description/icon.png"],
    "post_init_hook": "post_init_hook",
}
