{
    "name": "Planning Manufacturing",
    "summary": """""",
    "author": "Agro Marin",
    "website": "https://www.agromarin.mx",
    "license": "LGPL-3",
    "category": "Manufacturing/Manufacturing",
    "version": "saas~18.2.1.0.0",
    "depends": [
        "planning",
        "mrp",
        "hr",
    ],
    'data': [
        'security/res_groups_security.xml',
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/mrp_workcenter_views.xml',
        'views/planning_slot_views.xml',
        'views/planning_mrp_menus.xml',
    ],
    'installable': True,
    'application': True,
}
