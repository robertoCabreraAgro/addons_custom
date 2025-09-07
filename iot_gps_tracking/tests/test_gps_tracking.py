from odoo.tests import TransactionCase


class TestGPSTracking(TransactionCase):
    """Test GPS tracking functionality"""

    def setUp(self):
        super().setUp()

        # Create test IoT box
        self.test_box = self.env["iot.box"].create(
            {
                "name": "Test GPS Box",
                "identifier": "test_gps_box_001",
                "ip": "192.168.1.200",
                "version": "1.0",
            }
        )

        # Create test GPS configuration
        self.test_config = self.env["iot.gps.config"].create(
            {
                "name": "Test GPS Config",
                "protocol": "generic",
                "port": 8080,
                "update_interval": 60,
                "active": True,
            }
        )

        # Create test GPS device
        self.test_device = self.env["iot.device"].create(
            {
                "name": "Test GPS Device",
                "identifier": "test_gps_001",
                "type": "gps_tracker",
                "iot_id": self.test_box.id,
                "connection": "network",
                "gps_imei": "999888777666555",
                "gps_config_id": self.test_config.id,
            }
        )

    def test_01_gps_device_creation(self):
        """Test GPS device creation"""
        self.assertTrue(self.test_device)
        self.assertEqual(self.test_device.type, "gps_tracker")
        self.assertTrue(self.test_device.is_gps_device)
        self.assertEqual(self.test_device.gps_imei, "999888777666555")

    def test_02_process_gps_position(self):
        """Test processing GPS position data"""
        position_data = {
            "latitude": 40.7128,
            "longitude": -74.0060,
            "speed": 45.5,
            "altitude": 100,
            "satellites": 8,
            "battery": 85,
            "ignition": True,
            "movement": True,
        }

        # Enable tracking
        self.test_device.gps_tracking_enabled = True

        # Process position
        tracking_point = self.test_device.process_gps_position(position_data)

        # Verify device updated
        self.assertEqual(self.test_device.gps_last_latitude, 40.7128)
        self.assertEqual(self.test_device.gps_last_longitude, -74.0060)
        self.assertEqual(self.test_device.gps_last_speed, 45.5)
        self.assertEqual(self.test_device.gps_battery_level, 85)

        # Verify tracking point created
        self.assertTrue(tracking_point)
        self.assertEqual(tracking_point.latitude, 40.7128)
        self.assertEqual(tracking_point.longitude, -74.0060)

    def test_03_geofence_circle(self):
        """Test circular geofence"""
        geofence = self.env["iot.gps.geofence"].create(
            {
                "name": "Test Circle Geofence",
                "geofence_type": "circle",
                "center_latitude": 40.7128,
                "center_longitude": -74.0060,
                "radius": 1000,
                "active": True,
            }
        )

        # Test point inside
        is_inside = geofence._is_point_inside(40.7128, -74.0060)
        self.assertTrue(is_inside)

        # Test point outside
        is_outside = geofence._is_point_inside(40.8000, -74.0000)
        self.assertFalse(is_outside)

    def test_04_tracking_point_creation(self):
        """Test tracking point creation from IoT data"""
        position_data = {
            "latitude": 40.7128,
            "longitude": -74.0060,
            "speed": 30,
            "altitude": 95,
            "satellites": 7,
            "accuracy": 5.2,
            "ignition": True,
            "movement": True,
            "odometer": 12345.6,
            "fuel_level": 75,
        }

        tracking_point = self.env["iot.gps.tracking.point"].create_from_iot_data(
            self.test_device.id, position_data
        )

        self.assertTrue(tracking_point)
        self.assertEqual(tracking_point.iot_device_id.id, self.test_device.id)
        self.assertEqual(tracking_point.latitude, 40.7128)
        self.assertEqual(tracking_point.longitude, -74.0060)
        self.assertEqual(tracking_point.speed, 30)
        self.assertEqual(tracking_point.odometer, 12345.6)
        self.assertEqual(tracking_point.fuel_level, 75)

    def test_05_config_device_association(self):
        """Test GPS configuration and device association"""
        self.assertEqual(self.test_device.gps_config_id, self.test_config)
        self.assertEqual(self.test_config.device_count, 1)
        self.assertIn(self.test_device, self.test_config.device_ids)

    def test_06_tracking_history(self):
        """Test tracking history"""
        # Create multiple tracking points
        for i in range(5):
            self.env["iot.gps.tracking.point"].create(
                {
                    "iot_device_id": self.test_device.id,
                    "latitude": 40.7128 + (i * 0.001),
                    "longitude": -74.0060 + (i * 0.001),
                    "speed": 30 + i * 5,
                    "satellites": 7,
                }
            )

        # Check tracking point count
        self.assertEqual(self.test_device.gps_tracking_point_count, 5)
        self.assertEqual(len(self.test_device.gps_tracking_point_ids), 5)
