{
    "name": "Command Palette Record Search",
    "version": "saas~18.4.0.0.1",
    "summary": "Search Odoo records from the command palette",
    "author": "Mohammed Shahil",
    "website": "http://www.shahil.info",
    "license": "OPL-1",
    "category": "Extra Tools",
    "depends": ["web"],
    "data": [
        "security/ir.model.access.csv",
    ],
    "assets": {
        "web.assets_backend": [
            "ms_quick_record_seach/static/src/js/record_search_provider.js",
        ],
    },
    "installable": True,
    "application": False,
}
