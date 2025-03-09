
{
    "name": "GPS Tracking",
    "version": "1.0",
    "category": "Fleet Management",
    "summary": "Module to track GPS coordinates and display them on a map",
    "author": "Raúl Alejandro Rodríguez López",
    "website": "https://raulalejandro.com.mx",
    "depends": ["fleet"], 
    "data": [
        "security/ir.model.access.csv",
        "views/gps_tracking_device_views.xml",
        "views/gps_tracking_menus.xml", # Last because referencing actions defined in previous files
    ], 
    "demo": [
        "demo/gps_tracking_device_data.xml",
        "demo/gps_tracking_point_data.xml",
    ],
    #"assets": {
    #    "web.assets_backend": [
    #    "gps_tracking/static/src/**/*"
    #    ],
    #},
    "installable": True,
    "application": True,
}
