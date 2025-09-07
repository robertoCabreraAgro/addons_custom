# IoT GPS Tracking Module

## Overview
This module integrates GPS tracking devices with Odoo's IoT framework, providing real-time vehicle tracking, geofencing, and telemetry monitoring capabilities.

## Features

### Core Functionality
- **GPS Device Management**: Register and manage GPS tracking devices as IoT devices
- **Real-time Tracking**: WebSocket-based real-time position updates
- **Historical Tracking**: Store and analyze historical GPS tracking points
- **Geofencing**: Create and monitor geographical boundaries with alerts
- **Multi-protocol Support**: Compatible with Teltonika, Queclink, Concox, and generic GPS protocols

### Technical Features
- Network-based GPS driver for IoT framework
- RESTful webhook endpoints for GPS data ingestion
- Batch processing for multiple device updates
- Configurable data retention and compression
- Integration with base_geoengine for spatial operations

## Installation

1. Ensure dependencies are installed:
   - `iot` - IoT framework base module
   - `iot_base` - IoT base functionality
   - `base_geoengine` - Geographic/spatial field support

2. Place this module in your Odoo addons path
3. Update the module list
4. Install "IoT GPS Tracking" from Apps

## Configuration

### GPS Device Setup
1. Navigate to IoT > GPS Tracking > GPS Devices
2. Create a new GPS device or auto-register via webhook
3. Configure tracking parameters:
   - Update interval (seconds)
   - Tracking enabled/disabled
   - Associated GPS configuration profile

### Webhook Integration
The module provides webhook endpoints for GPS data:

```
POST /gps/iot/webhook
{
    "imei": "device_imei",
    "data": {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "timestamp": "2024-01-15T10:30:00",
        "speed": 45.5,
        "altitude": 100,
        "satellites": 8
    }
}
```

### Geofencing
1. Navigate to IoT > GPS Tracking > Geofencing > Geofences
2. Create geofence zones (circle, polygon, or rectangle)
3. Configure alerts:
   - Entry alerts
   - Exit alerts
   - Dwell time alerts
4. Assign devices to monitor

## API Endpoints

- `/gps/iot/webhook` - Receive GPS position data
- `/gps/iot/status/<imei>` - Get device status
- `/gps/iot/command` - Send commands to devices
- `/gps/iot/batch` - Batch update multiple devices

## Models

### iot.gps.tracking.point
Stores GPS position data with full telemetry:
- Position: latitude, longitude, altitude
- Motion: speed, heading, movement state
- Quality: satellites, accuracy, HDOP/PDOP
- Telemetry: fuel level, engine data, battery voltage

### iot.gps.config
Configuration profiles for GPS devices:
- Protocol settings
- Update intervals
- Alert thresholds
- Data retention policies

### iot.gps.geofence
Geographical boundaries for monitoring:
- Shape types: circle, polygon, rectangle
- Alert configurations
- Schedule settings
- Device associations

## Security

Two security groups are provided:
- **GPS Tracking User**: View tracking data and device positions
- **GPS Tracking Manager**: Full configuration and management access

## IoT Driver

The module includes `GPSNetworkDriver` which:
- Handles network-connected GPS devices
- Processes GPS data through queues
- Manages real-time position updates
- Supports various GPS data formats

## Usage Examples

### Starting Tracking
```python
device = env['iot.device'].search([('gps_imei', '=', 'YOUR_IMEI')])
device.action_start_tracking()
```

### Processing GPS Data
```python
position_data = {
    'latitude': 40.7128,
    'longitude': -74.0060,
    'speed': 45.5,
    'satellites': 8
}
device.process_gps_position(position_data)
```

### Checking Geofence
```python
geofence = env['iot.gps.geofence'].browse(geofence_id)
is_inside = geofence._is_point_inside(latitude, longitude)
```

## License
LGPL-3