{
    "name": "Estate OWL Dashboard",
    "version": "1.6",
    "summary": "Real Estate OWL Widget Dashboard - Extension for Estate",
    "category": "Real Estate",
    "author": "JEM",
    "depends": ["base", "web", "estate"],
    "data": [
        "views/estate_action.xml",
        "views/estate_menu.xml"
    ],
    "assets": {
        "web.assets_backend": [
            "https://cdn.jsdelivr.net/npm/chart.js",
            "estate_owl/static/src/css/estate_widget.css",
            "estate_owl/static/src/js/estate_widget.js",
            "estate_owl/static/src/js/estate_client_action.js",
            "estate_owl/static/src/xml/estate_widget.xml",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
