{
    "name": "Units of measure extended",
    "description": """
        This is the base module for managing Units of measure.
        ========================================================================
    """,
    "version": "19.0.1.0.0",
    "category": "Sales/Sales",
    "author": "Luis Marin",
    "website": "https://agromarin.mx",
    "depends": [
        "product",
    ],
    "data": [
        "data/uom_uom_data.xml",
        "wizard/res_config_settings_views.xml",
    ],
    "installable": True,
    "license": "AGPL-3",
    "post_init_hook": "post_init_hook",
}
