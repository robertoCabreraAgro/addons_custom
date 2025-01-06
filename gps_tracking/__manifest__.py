
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
        'views/gps_tracking_device_views.xml',
        'views/gps_tracking_log_views.xml',
        'views/geoengine_raster_layer_data.xml',
        'views/geoengine_vector_layer_data.xml',
        # 'views/gps_tracking_point_views2.xml',
        # 'wizard/gps_tracking_data_history.xml',
    ], 
    'assets': {
        'web.assets_backend': [
            'gps_tracking/static/src/**/*'
        ],
    },
    'installable': True,
    'application': True,
    'external_dependencies': {'python' : ['pyproj']}
}
