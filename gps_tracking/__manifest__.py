{
    'name': 'GPS Tracking',
    'version': '1.0',
    'category': 'Fleet Management',
    'summary': 'Module to track GPS coordinates and display them on a map',
    'author': 'Raúl Alejandro Rodríguez López',
    'website': 'https://raulalejandro.com.mx',
    'depends': ['base_geoengine'], 
    'data': [
        'security/ir.model.access.csv',
        'views/gps_tracking_views.xml',
        'views/gps_views.xml',
        'views/gps_split_view.xml',
    ], 
    'assets': {
        'web.assets_backend': [
        'gps_tracking/static/src/**/*'
        ],
    },
    'installable': True,
    'application': True,
}