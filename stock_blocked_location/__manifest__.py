{
    'name': 'Block Location Outgoing',
    'version': 'saas~18.2.0.0.1',
    'summary': 'Block outgoing operations from specific stock locations',
    'category': 'Warehouse',
    'author': 'Robert',
    'website': 'https://www.agromarin.mx',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'stock',
        'mail',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/stock_location_view.xml',
    ],
    'installable': True,
    'application': False,
}