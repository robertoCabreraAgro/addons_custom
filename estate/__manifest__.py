{
    'name': 'Real Estate',
    'version': '1.0',
    'summary': 'Manage real estate properties',
    'category': 'Real Estate',
    'sequence': 10,
    'depends': ['base', 'web'],

    'data': [
        'security/estate_security.xml',
        'security/ir.model.access.csv',
        'views/estate_property_views.xml',
        'views/estate_property_type_views.xml',
        'views/estate_property_tag_views.xml',
        'views/estate_property_offer_views.xml',
        'wizards/estate_property_offer_wizard_views.xml',
        'views/estate_property_offer_actions.xml',
        'views/estate_property_type_actions.xml',
        'views/estate_property_tag_actions.xml',
        'views/estate_menus.xml',
        'views/inherited_views.xml',
        'report/estate_property_report.xml',
        'report/estate_property_report_views.xml',
    ],

        'installable': True,
        'application': True,
        'auto_install': False,

        'assets': {

    },
}