# -*- coding: utf-8 -*-

{
    "name": "Power User",
    "description": "Execute PostgreSQL query and python into Odoo interface",
    "category": "Productivity/Productivity",
    "author": "Luis Marin",
    "website": "https://github.com/YvanDotet/query_deluxe/",
    "version": "1.0",
    "depends": [
        "base",
        "mail",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/data.xml",
        "views/power_user_views.xml",
        "report/print_pdf.xml",
        "wizard/pdforientation.xml",
        ],
    "images": ["static/description/banner.gif"],
    "license": "AGPL-3",
    "installable": True,
}