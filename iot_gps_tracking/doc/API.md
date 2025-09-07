# IoT GPS Tracking API Documentation

## REST API Endpoints

### 1. GPS Data Webhook
**Endpoint:** `/gps/iot/webhook`  
**Method:** POST  
**Authentication:** Public (consider adding API key authentication in production)  
**Content-Type:** application/json

#### Request Body
```json
{
    "imei": "123456789012345",
    "data": {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "timestamp": "2024-01-15T10:30:00",
        "speed": 45.5,
        "altitude": 100,
        "satellites": 8,
        "accuracy": 5.2,
        "heading": 180,
        "battery": 85,
        "ignition": true,
        "movement": true,
        "odometer": 12543.6,
        "fuel_level": 75,
        "engine_temp": 85.5,
        "engine_rpm": 2500,
        "battery_voltage": 12.8,
        "external_voltage": 13.5,
        "gsm_signal": 4
    }
}
```

#### Response
```json
{
    "status": "success",
    "device_id": 123,
    "tracking_point_id": 456,
    "message": "GPS data received and processed"
}
```

#### Error Response
```json
{
    "status": "error",
    "message": "Error description"
}
```

### 2. Device Status
**Endpoint:** `/gps/iot/status/<imei>`  
**Method:** GET  
**Authentication:** Public

#### Response
```json
{
    "status": "success",
    "device": {
        "id": 123,
        "name": "Vehicle Tracker 1",
        "imei": "123456789012345",
        "connected": true,
        "tracking_enabled": true,
        "last_update": "2024-01-15T10:30:00",
        "last_position": {
            "latitude": 40.7128,
            "longitude": -74.0060,
            "speed": 45.5,
            "altitude": 100
        },
        "battery_level": 85,
        "ignition": true,
        "movement": true
    }
}
```

### 3. Send Command
**Endpoint:** `/gps/iot/command`  
**Method:** POST  
**Authentication:** Public  
**Content-Type:** application/json

#### Request Body
```json
{
    "imei": "123456789012345",
    "command": "start_tracking",
    "params": {
        "interval": 30
    }
}
```

#### Available Commands
- `start_tracking` - Start GPS tracking
- `stop_tracking` - Stop GPS tracking
- `get_position` - Request current position
- `set_interval` - Set tracking interval (requires `interval` param)

#### Response
```json
{
    "status": "success",
    "message": "Command start_tracking sent to device 123456789012345"
}
```

### 4. Batch Update
**Endpoint:** `/gps/iot/batch`  
**Method:** POST  
**Authentication:** Public  
**Content-Type:** application/json

#### Request Body
```json
{
    "updates": [
        {
            "imei": "123456789012345",
            "data": {
                "latitude": 40.7128,
                "longitude": -74.0060,
                "speed": 45.5
            }
        },
        {
            "imei": "543210987654321",
            "data": {
                "latitude": 40.7580,
                "longitude": -73.9855,
                "speed": 0
            }
        }
    ]
}
```

#### Response
```json
{
    "status": "success",
    "processed": 2,
    "results": [
        {
            "status": "success",
            "device_id": 123,
            "tracking_point_id": 456
        },
        {
            "status": "success",
            "device_id": 124,
            "tracking_point_id": 457
        }
    ]
}
```

## Python API

### Creating GPS Device
```python
from odoo import api, fields, models

# Create GPS device
device = env['iot.device'].create_gps_device(
    imei='123456789012345',
    initial_data={
        'latitude': 40.7128,
        'longitude': -74.0060,
        'speed': 45.5
    }
)
```

### Processing Position Data
```python
# Process incoming GPS position
position_data = {
    'latitude': 40.7128,
    'longitude': -74.0060,
    'speed': 45.5,
    'altitude': 100,
    'satellites': 8,
    'battery': 85,
    'ignition': True,
    'movement': True
}

tracking_point = device.process_gps_position(position_data)
```

### Managing Tracking
```python
# Start tracking
device.action_start_tracking()

# Stop tracking
device.action_stop_tracking()

# Get current position
device.action_get_current_position()

# View tracking history
device.action_view_tracking_points()
```

### Working with Geofences
```python
# Create circular geofence
geofence = env['iot.gps.geofence'].create({
    'name': 'Warehouse Zone',
    'geofence_type': 'circle',
    'center_latitude': 40.7128,
    'center_longitude': -74.0060,
    'radius': 500,
    'alert_on_enter': True,
    'alert_on_exit': True,
    'device_ids': [(4, device.id)]
})

# Check if point is inside geofence
is_inside = geofence._is_point_inside(40.7128, -74.0060)

# Check device position against geofence
alerts = geofence.check_device_position(
    device.id,
    device.gps_last_latitude,
    device.gps_last_longitude
)
```

### Creating Tracking Points
```python
# Create from IoT data
tracking_point = env['iot.gps.tracking.point'].create_from_iot_data(
    iot_device_id=device.id,
    position_data={
        'latitude': 40.7128,
        'longitude': -74.0060,
        'speed': 45.5,
        'timestamp': '2024-01-15T10:30:00'
    },
    session_id=123
)

# Direct creation
tracking_point = env['iot.gps.tracking.point'].create({
    'iot_device_id': device.id,
    'latitude': 40.7128,
    'longitude': -74.0060,
    'speed': 45.5,
    'altitude': 100,
    'satellites': 8,
    'ignition': True,
    'movement': True
})
```

## JavaScript API

### GPS Device Controller
```javascript
import { GPSDeviceController } from '@iot_gps_tracking/js/gps_device_controller';

// Initialize controller
const controller = new GPSDeviceController({
    device: deviceData,
    onPositionUpdate: (deviceId) => {
        console.log(`Position updated for device ${deviceId}`);
    }
});

// Control tracking
await controller.startTracking();
await controller.stopTracking();
await controller.getCurrentPosition();
await controller.viewOnMap();
await controller.viewTrackingHistory();
```

### Real-time Tracker
```javascript
import { GPSRealtimeTracker } from '@iot_gps_tracking/js/gps_realtime_tracker';

// Initialize real-time tracker
const tracker = new GPSRealtimeTracker({
    deviceIds: [123, 124, 125],
    updateInterval: 30000, // 30 seconds
    onUpdate: (deviceId, position) => {
        console.log(`Device ${deviceId} at ${position.latitude}, ${position.longitude}`);
    }
});

// Get device markers for map
const markers = tracker.getDeviceMarkers();
```

## WebSocket Events

### Subscribing to GPS Updates
```javascript
// Subscribe to position updates
busService.subscribe('gps_position_update', (message) => {
    const { device_id, position } = message;
    console.log(`Device ${device_id} position:`, position);
});

// Subscribe to device status changes
busService.subscribe('gps_device_status', (message) => {
    const { device_id, status } = message;
    console.log(`Device ${device_id} status:`, status);
});
```

## Authentication & Security

### API Key Authentication (Recommended)
Add API key validation to your endpoints:

```python
def validate_api_key(api_key):
    """Validate API key for webhook access"""
    valid_keys = request.env['ir.config_parameter'].sudo().get_param('gps.api_keys', '').split(',')
    return api_key in valid_keys

@http.route('/gps/iot/webhook', type='json', auth='public', methods=['POST'], csrf=False)
def gps_iot_webhook(self, api_key=None, **kwargs):
    if not validate_api_key(api_key):
        return {'status': 'error', 'message': 'Invalid API key'}
    # Process request...
```

### Rate Limiting
Implement rate limiting to prevent abuse:

```python
from werkzeug.contrib.cache import SimpleCache
cache = SimpleCache()

def rate_limit(ip_address, max_requests=100):
    """Simple rate limiting by IP"""
    key = f'rate_limit_{ip_address}'
    count = cache.get(key) or 0
    if count >= max_requests:
        return False
    cache.set(key, count + 1, timeout=3600)  # 1 hour window
    return True
```

## Error Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request - Invalid data format |
| 401 | Unauthorized - Invalid API key |
| 404 | Not Found - Device not found |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error |

## Best Practices

1. **Always validate input data** - Check latitude/longitude ranges, IMEI format
2. **Implement authentication** - Use API keys or OAuth for production
3. **Add rate limiting** - Prevent abuse and DoS attacks
4. **Log all API calls** - For debugging and audit trails
5. **Use HTTPS** - Encrypt data in transit
6. **Batch updates when possible** - Reduce API calls and improve performance
7. **Handle errors gracefully** - Return meaningful error messages
8. **Monitor API usage** - Track performance and usage patterns