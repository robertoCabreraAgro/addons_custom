{
    "name": "Marin RMA",
    "summary": """This module creates a master catalog for normalizing and categorizing customer claims.""",
    "author": "Agro Marin",
    "website": "https://www.agromarin.mx",
    "license": "LGPL-3",
    "category": "Hidden",
    "version": "saas~18.2.0.0.1",
    "depends": ["mail", "sale", "mrp"],
    "data": [
        "security/ir.model.access.csv",
        "views/rma_reason_views.xml",
        "views/rma_menus.xml"
    ],
    "installable": True,
}
