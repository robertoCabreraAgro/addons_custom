{
    "name": "IoT GPS Tracking",
    "version": "18.0.1.0.0",
    "category": "Internet of Things (IoT)/Fleet",
    "summary": "GPS Tracking integration with IoT framework",
    "description": """
IoT GPS Tracking
================

This module integrates GPS tracking devices with Odoo's IoT framework, providing:

Features:
---------
* GPS devices as IoT devices
* Real-time position tracking via WebSocket
* Geofence monitoring
* Route tracking and history
* Integration with fleet management
* Support for multiple GPS protocols
* Backward compatibility with existing GPS webhook

Technical Features:
------------------
* Network-based GPS driver for IoT framework
* WebSocket communication for real-time updates
* Migration wizard for existing GPS devices
* JavaScript GPS device controller
* Map visualization components
    """,
    "author": "Your Company",
    "website": "https://www.yourcompany.com",
    "depends": [
        "iot",
        "iot_base",
        "base_geoengine",  # For GeoPoint fields
    ],
    "data": [
        "security/iot_gps_security.xml",
        "security/ir.model.access.csv",
        "data/iot_device_type_data.xml",
        "data/iot_gps_cron.xml",
        "views/iot_device_views.xml",
        "views/iot_box_views.xml",
        "views/gps_tracking_point_views.xml",
        "views/iot_gps_config_views.xml",
        "views/iot_gps_geofence_views.xml",
        "views/iot_gps_menus.xml",
        "report/gps_tracking_report.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "iot_gps_tracking/static/src/**/*",
        ],
    },
    "demo": [
        "demo/iot_gps_demo.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
}
