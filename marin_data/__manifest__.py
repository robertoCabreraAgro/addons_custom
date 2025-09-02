{
    "name": "Marin Data",
    "summary": """
    Instance creator for Marin. This is the app data.
    """,
    "author": "AgroMarin",
    "website": "https://www.agromarin.mx",
    "license": "OPL-1",
    "category": "Installer",
    "version": "1.1",
    "depends": [
        "marin",
    ],
    "post_init_hook": "_post_init_marin",
    "installable": True,
    "application": False,
}
