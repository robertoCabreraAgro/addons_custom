# IoT GPS Tracking Module - Installation Guide

## Prerequisites

### System Requirements
- Odoo 18.0 or higher
- PostgreSQL 13+ with PostGIS extension
- Python 3.10+
- 2GB RAM minimum (4GB recommended)
- 10GB disk space for tracking data

### Required Odoo Modules
1. **iot** - IoT framework base module
2. **iot_base** - IoT base functionality  
3. **base_geoengine** - Geographic/spatial field support

## Installation Steps

### 1. Install System Dependencies

#### Ubuntu/Debian
```bash
# Install PostGIS
sudo apt-get update
sudo apt-get install postgresql-13-postgis-3 postgis

# Install Python dependencies
sudo apt-get install python3-pip python3-dev
sudo apt-get install libgeos-dev libproj-dev gdal-bin

# Install Python packages
pip3 install shapely pyproj
```

#### CentOS/RHEL
```bash
# Install PostGIS
sudo yum install postgis30_13
sudo yum install postgis30-utils

# Install Python dependencies
sudo yum install python3-pip python3-devel
sudo yum install geos-devel proj-devel gdal

# Install Python packages
pip3 install shapely pyproj
```

### 2. Enable PostGIS in Database

```sql
-- Connect to your Odoo database
psql -U postgres -d your_odoo_db

-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Verify installation
SELECT PostGIS_version();
```

### 3. Install Required Odoo Modules

1. Download and install **base_geoengine** module:
```bash
cd /opt/odoo/addons_custom
git clone https://github.com/OCA/geospatial.git
cp -r geospatial/base_geoengine .
```

2. Install IoT modules (if not already installed):
   - Go to Apps → Search for "IoT"
   - Install "Internet of Things" and "IoT Base"

### 4. Install IoT GPS Tracking Module

1. Copy module to addons directory:
```bash
cp -r iot_gps_tracking /opt/odoo/addons_custom/
```

2. Update module list:
```bash
./odoo-bin -c /etc/odoo.conf -d your_db --update-list
```

3. Install from Odoo interface:
   - Go to Apps → Update Apps List
   - Search for "IoT GPS Tracking"
   - Click Install

### 5. Initial Configuration

#### Configure GPS Devices

1. Navigate to **IoT → GPS Tracking → Configuration → GPS Configurations**
2. Create a configuration profile:
   ```
   Name: Default GPS Config
   Protocol: Generic
   Update Interval: 30 seconds
   Data Retention: 90 days
   ```

3. Register GPS devices:
   - Go to **IoT → GPS Tracking → Tracking → GPS Devices**
   - Click Create
   - Enter device details:
     ```
     Name: Vehicle Tracker 1
     IMEI: Your device IMEI
     Configuration: Default GPS Config
     Tracking Enabled: Yes
     ```

#### Set Up Geofences

1. Navigate to **IoT → GPS Tracking → Geofencing → Geofences**
2. Create a geofence:
   ```
   Name: Main Warehouse
   Type: Circle
   Center Latitude: Your latitude
   Center Longitude: Your longitude
   Radius: 500 meters
   Alert on Enter: Yes
   Alert on Exit: Yes
   ```

3. Assign devices to monitor

#### Configure Webhooks

1. Configure your GPS device to send data to:
   ```
   https://your-odoo-domain.com/gps/iot/webhook
   ```

2. Test with curl:
   ```bash
   curl -X POST https://your-odoo-domain.com/gps/iot/webhook \
     -H "Content-Type: application/json" \
     -d '{
       "imei": "123456789012345",
       "data": {
         "latitude": 40.7128,
         "longitude": -74.0060,
         "speed": 45.5
       }
     }'
   ```

### 6. Security Configuration

#### Set Up User Groups

1. Go to **Settings → Users & Companies → Groups**
2. Assign users to GPS groups:
   - **GPS Tracking User** - View access
   - **GPS Tracking Manager** - Full access

#### Configure API Security

1. Add API keys (optional):
   ```python
   # In Settings → Technical → Parameters → System Parameters
   Key: gps.api_keys
   Value: your-secret-key-1,your-secret-key-2
   ```

2. Configure HTTPS (required for production):
   ```nginx
   server {
       listen 443 ssl;
       server_name your-domain.com;
       
       ssl_certificate /path/to/certificate.crt;
       ssl_certificate_key /path/to/private.key;
       
       location / {
           proxy_pass http://localhost:8069;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

### 7. Performance Optimization

#### Database Indexes
Run these SQL commands for better performance:

```sql
-- Index for tracking points
CREATE INDEX idx_tracking_point_device_timestamp 
ON iot_gps_tracking_point(iot_device_id, timestamp DESC);

CREATE INDEX idx_tracking_point_location 
ON iot_gps_tracking_point(latitude, longitude);

-- Spatial index for geofences
CREATE INDEX idx_geofence_geom 
ON iot_gps_geofence USING GIST(the_geom);

-- Index for device lookups
CREATE INDEX idx_device_imei 
ON iot_device(gps_imei) WHERE type = 'gps_tracker';
```

#### Configure Cron Jobs
Verify cron jobs are active:

1. Go to **Settings → Technical → Automation → Scheduled Actions**
2. Check these are enabled:
   - GPS: Clean Old Tracking Points (daily)
   - GPS: Check Device Status (10 minutes)
   - GPS: Process Geofence Alerts (5 minutes)

### 8. Testing

#### Test Device Registration
```python
# Odoo shell
./odoo-bin shell -c /etc/odoo.conf -d your_db

# Create test device
device = env['iot.device'].create_gps_device(
    imei='TEST123456789',
    initial_data={'latitude': 40.7128, 'longitude': -74.0060}
)
print(f"Device created: {device.name}")
```

#### Test Position Update
```python
# Process test position
position_data = {
    'latitude': 40.7128,
    'longitude': -74.0060,
    'speed': 45.5,
    'satellites': 8
}
tracking_point = device.process_gps_position(position_data)
print(f"Tracking point created: {tracking_point.id}")
```

#### Test Geofence
```python
# Test geofence detection
geofence = env['iot.gps.geofence'].search([], limit=1)
is_inside = geofence._is_point_inside(40.7128, -74.0060)
print(f"Point inside geofence: {is_inside}")
```

## Troubleshooting

### Common Issues

#### PostGIS Not Found
```
Error: type "geometry" does not exist
```
**Solution:** Enable PostGIS extension in database (see step 2)

#### Module Not Found
```
Error: No module named 'shapely'
```
**Solution:** Install Python dependencies:
```bash
pip3 install shapely pyproj
```

#### Permission Denied
```
Error: Access denied for GPS tracking
```
**Solution:** Add user to GPS Tracking User group

#### No GPS Data Received
**Check:**
1. Device is sending to correct webhook URL
2. Firewall allows incoming connections
3. HTTPS certificate is valid
4. Check logs: `/var/log/odoo/odoo.log`

### Debug Mode

Enable debug logging:
```python
# In GPS Configuration
Debug Mode: True
Log Level: debug
```

Check logs:
```bash
tail -f /var/log/odoo/odoo.log | grep GPS
```

## Upgrade Instructions

### From Previous Version

1. Backup database:
```bash
pg_dump your_db > backup.sql
```

2. Update module:
```bash
./odoo-bin -c /etc/odoo.conf -d your_db -u iot_gps_tracking
```

3. Run migrations (if any):
   - Migrations run automatically during upgrade

### Rollback Procedure

1. Restore database:
```bash
psql your_db < backup.sql
```

2. Restore module files:
```bash
cp -r iot_gps_tracking.backup iot_gps_tracking
```

## Support

For issues or questions:
1. Check documentation in `/doc` folder
2. Review API documentation in `/doc/API.md`
3. Check test cases in `/tests` folder
4. Contact support with:
   - Odoo version
   - Module version
   - Error logs
   - Steps to reproduce