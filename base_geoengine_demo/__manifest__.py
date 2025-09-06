{
    "name": "Geo spatial support Demo",
    "category": "GeoBI",
    "author": "Camptocamp,Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "website": "https://github.com/OCA/geospatial",
    "depends": ["base_geoengine"],
    "data": [
        "security/ir.model.access.csv",
        "data/npa_geom.xml",
        "data/retail_machine_geom.xml",
        "views/dummy_zip_views.xml",
        "views/retailing_machine_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": True,
}
