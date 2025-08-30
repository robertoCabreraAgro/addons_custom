{
    "name": "Discuss Alerts",
    "summary": """Configure discussion channels to automatically post alerts based on custom criteria""",
    "author": "Agro Marin",
    "website": "https://www.agromarin.mx",
    "license": "LGPL-3",
    "category": "Hidden",
    "version": "saas~18.2.0.0.1",
    "depends": ["mail", "sale"],
    "data": [
        "data/ir_cron_data.xml",
        "views/discuss_channel_views.xml",
    ],
    "installable": True,
}
