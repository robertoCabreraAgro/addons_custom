import logging

from datetime import datetime
from threading import Lock
from queue import Queue, Empty

from odoo.addons.iot_drivers.driver import Driver
from odoo.addons.iot_drivers.event_manager import event_manager

_logger = logging.getLogger(__name__)


class GPSNetworkDriver(Driver):
    """Driver for network-connected GPS tracking devices

    This driver handles GPS devices that communicate via network protocols
    (HTTP webhooks, TCP/IP, etc.) rather than direct serial/USB connections.
    """

    connection_type = "network"
    priority = 10  # Higher priority for network GPS devices

    def __init__(self, identifier, device):
        super().__init__(identifier, device)
        self.device_type = "gps_tracker"
        self.device_manufacturer = device.get("manufacturer", "Generic GPS")
        self.device_name = f"GPS Tracker {identifier}"
        self.device_connection = "network"

        # GPS-specific attributes
        self.gps_queue = Queue(maxsize=1000)  # Buffer for incoming GPS data
        self._last_position = None
        self._tracking_enabled = False
        self._tracking_interval = 30  # seconds
        self._position_lock = Lock()
        self._geofences = []

        # Statistics
        self._total_points = 0
        self._last_update = None

        # Register GPS-specific actions
        self._actions.update(
            {
                "get_position": self._get_position,
                "get_status": self._get_status,
                "start_tracking": self._start_tracking,
                "stop_tracking": self._stop_tracking,
                "set_interval": self._set_tracking_interval,
                "get_history": self._get_history,
                "check_geofence": self._check_geofence,
                "add_geofence": self._add_geofence,
                "remove_geofence": self._remove_geofence,
                "process_gps_data": self._process_gps_data,
                "clear_queue": self._clear_queue,
            }
        )

        _logger.info(f"GPS Network Driver initialized for device {identifier}")

    @classmethod
    def supported(cls, device):
        """Check if device is a network-connected GPS tracker

        :param device: Device information dictionary
        :return: True if this driver supports the device
        """
        # Check various indicators that this is a GPS device
        device_type = device.get("type", "").lower()
        identifier = device.get("identifier", "").lower()
        manufacturer = device.get("manufacturer", "").lower()

        is_gps = (
            device_type == "gps_tracker"
            or "gps" in device_type
            or "gps" in identifier
            or "tracker" in identifier
            or "teltonika" in manufacturer
            or "queclink" in manufacturer
            or "concox" in manufacturer
        )

        # Must be network-connected
        is_network = device.get("connection") == "network"

        return is_gps and is_network

    def _get_position(self, data=None):
        """Get current GPS position

        :return: Dictionary with current position data
        """
        with self._position_lock:
            if self._last_position:
                return {
                    "status": "success",
                    "position": self._last_position,
                    "timestamp": (
                        self._last_update.isoformat() if self._last_update else None
                    ),
                    "tracking_enabled": self._tracking_enabled,
                }
            return {
                "status": "error",
                "message": "No position available",
                "tracking_enabled": self._tracking_enabled,
            }

    def _get_status(self, data=None):
        """Get device status and statistics

        :return: Dictionary with device status
        """
        with self._position_lock:
            age_seconds = None
            if self._last_update:
                age_seconds = (datetime.now() - self._last_update).total_seconds()

            return {
                "status": "success",
                "device_id": self.device_identifier,
                "tracking_enabled": self._tracking_enabled,
                "tracking_interval": self._tracking_interval,
                "total_points": self._total_points,
                "queue_size": self.gps_queue.qsize(),
                "last_update": (
                    self._last_update.isoformat() if self._last_update else None
                ),
                "age_seconds": age_seconds,
                "has_position": self._last_position is not None,
                "geofences_count": len(self._geofences),
            }

    def _start_tracking(self, data=None):
        """Start continuous GPS tracking

        :return: Status dictionary
        """
        self._tracking_enabled = True
        _logger.info(f"GPS tracking started for device {self.device_identifier}")

        # Notify listeners
        event_manager.device_changed(
            self,
            {
                "type": "tracking_status",
                "device_id": self.device_identifier,
                "tracking_enabled": True,
                "timestamp": datetime.now().isoformat(),
            },
        )

        return {"status": "success", "message": "Tracking started"}

    def _stop_tracking(self, data=None):
        """Stop GPS tracking

        :return: Status dictionary
        """
        self._tracking_enabled = False
        _logger.info(f"GPS tracking stopped for device {self.device_identifier}")

        # Notify listeners
        event_manager.device_changed(
            self,
            {
                "type": "tracking_status",
                "device_id": self.device_identifier,
                "tracking_enabled": False,
                "timestamp": datetime.now().isoformat(),
            },
        )

        return {"status": "success", "message": "Tracking stopped"}

    def _set_tracking_interval(self, data):
        """Set tracking interval in seconds

        :param data: Dictionary with 'interval' key
        :return: Status dictionary
        """
        interval = data.get("interval", 30)
        if not isinstance(interval, (int, float)) or interval < 1:
            return {"status": "error", "message": "Invalid interval"}

        self._tracking_interval = interval
        return {"status": "success", "interval": interval}

    def _process_gps_data(self, data):
        """Process incoming GPS data

        :param data: Dictionary with GPS data
        :return: Status dictionary
        """
        try:
            gps_data = data.get("gps_data", {})

            # Add to queue for processing
            if not self.gps_queue.full():
                self.gps_queue.put(gps_data)
            else:
                _logger.warning(f"GPS queue full for device {self.device_identifier}")
                # Remove oldest item and add new one
                try:
                    self.gps_queue.get_nowait()
                    self.gps_queue.put(gps_data)
                except Empty:
                    pass

            return {"status": "success", "queued": True}

        except Exception as e:
            _logger.error(f"Error processing GPS data: {e}")
            return {"status": "error", "message": str(e)}

    def _parse_gps_data(self, raw_data):
        """Parse raw GPS data into standard format

        :param raw_data: Raw GPS data dictionary
        :return: Standardized position dictionary
        """
        # Handle different GPS data formats
        position = {
            "latitude": None,
            "longitude": None,
            "timestamp": datetime.now().isoformat(),
            "speed": 0,
            "altitude": 0,
            "satellites": 0,
            "accuracy": 0,
            "heading": 0,
            "battery": 100,
            "ignition": False,
            "movement": False,
        }

        # Try to extract latitude/longitude
        position["latitude"] = (
            raw_data.get("latitude") or raw_data.get("lat") or raw_data.get("y")
        )
        position["longitude"] = (
            raw_data.get("longitude")
            or raw_data.get("lng")
            or raw_data.get("lon")
            or raw_data.get("x")
        )

        # Extract timestamp
        timestamp = raw_data.get("timestamp") or raw_data.get("ts")
        if timestamp:
            if isinstance(timestamp, str):
                position["timestamp"] = timestamp
            elif isinstance(timestamp, (int, float)):
                # Assume Unix timestamp
                position["timestamp"] = datetime.fromtimestamp(timestamp).isoformat()

        # Extract other fields
        position["speed"] = float(raw_data.get("speed", 0) or 0)
        position["altitude"] = float(
            raw_data.get("altitude", 0) or raw_data.get("alt", 0) or 0
        )
        position["satellites"] = int(
            raw_data.get("satellites", 0) or raw_data.get("sat", 0) or 0
        )
        position["accuracy"] = float(raw_data.get("accuracy", 0) or 0)
        position["heading"] = float(
            raw_data.get("heading", 0) or raw_data.get("angle", 0) or 0
        )
        position["battery"] = float(raw_data.get("battery", 100) or 100)
        position["ignition"] = bool(raw_data.get("ignition", False))
        position["movement"] = bool(raw_data.get("movement", False))

        # Additional telemetry
        if "odometer" in raw_data:
            position["odometer"] = float(raw_data["odometer"])
        if "fuel_level" in raw_data:
            position["fuel_level"] = float(raw_data["fuel_level"])
        if "engine_temp" in raw_data:
            position["engine_temp"] = float(raw_data["engine_temp"])

        return position

    def _check_geofence(self, data):
        """Check if current position is within a geofence

        :param data: Dictionary with geofence_id
        :return: Status dictionary
        """
        if not self._last_position:
            return {"status": "error", "message": "No position available"}

        geofence_id = data.get("geofence_id")
        # This would typically check against stored geofences
        # For now, return a placeholder
        return {
            "status": "success",
            "inside": False,
            "geofence_id": geofence_id,
            "position": self._last_position,
        }

    def _add_geofence(self, data):
        """Add a geofence for monitoring

        :param data: Geofence definition
        :return: Status dictionary
        """
        geofence = {
            "id": data.get("id"),
            "name": data.get("name", "Unnamed"),
            "type": data.get("type", "circle"),  # circle, polygon
            "coordinates": data.get("coordinates"),
            "radius": data.get("radius", 100),  # meters for circle type
        }
        self._geofences.append(geofence)
        return {"status": "success", "geofence": geofence}

    def _remove_geofence(self, data):
        """Remove a geofence

        :param data: Dictionary with geofence_id
        :return: Status dictionary
        """
        geofence_id = data.get("geofence_id")
        self._geofences = [g for g in self._geofences if g.get("id") != geofence_id]
        return {"status": "success", "removed": geofence_id}

    def _get_history(self, data):
        """Get tracking history (placeholder for now)

        :param data: Dictionary with date range
        :return: History data
        """
        return {
            "status": "success",
            "message": "History retrieval not yet implemented",
            "start_date": data.get("start_date"),
            "end_date": data.get("end_date"),
        }

    def _clear_queue(self, data=None):
        """Clear the GPS data queue

        :return: Status dictionary
        """
        size = self.gps_queue.qsize()
        while not self.gps_queue.empty():
            try:
                self.gps_queue.get_nowait()
            except Empty:
                break
        return {"status": "success", "cleared": size}

    def _process_position_update(self, position):
        """Process a position update and notify listeners

        :param position: Parsed position dictionary
        """
        with self._position_lock:
            self._last_position = position
            self._last_update = datetime.now()
            self._total_points += 1

        # Check geofences
        geofence_alerts = []
        for geofence in self._geofences:
            # Simplified geofence check (would need proper implementation)
            pass

        # Broadcast position update
        event_data = {
            "type": "gps_position",
            "device_id": self.device_identifier,
            "position": position,
            "timestamp": datetime.now().isoformat(),
            "tracking_enabled": self._tracking_enabled,
            "geofence_alerts": geofence_alerts,
        }

        # Update device data
        self.data["position"] = position
        self.data["last_update"] = self._last_update.isoformat()

        # Notify all listeners
        event_manager.device_changed(self, event_data)

        _logger.debug(
            f"GPS position updated for {self.device_identifier}: "
            f"lat={position.get('latitude')}, lon={position.get('longitude')}"
        )

    def run(self):
        """Main driver loop for processing GPS data

        This method runs in a separate thread and continuously
        processes GPS data from the queue.
        """
        _logger.info(f"GPS Network Driver thread started for {self.device_identifier}")

        while not self._stopped.is_set():
            try:
                # Check for GPS data in queue
                if not self.gps_queue.empty():
                    try:
                        # Get data with timeout to allow checking stopped flag
                        gps_data = self.gps_queue.get(timeout=0.1)

                        # Parse and process the GPS data
                        position = self._parse_gps_data(gps_data)

                        # Validate position
                        if (
                            position["latitude"] is not None
                            and position["longitude"] is not None
                        ):
                            if self._tracking_enabled:
                                self._process_position_update(position)
                        else:
                            _logger.warning(
                                f"Invalid GPS data received for {self.device_identifier}"
                            )

                    except Empty:
                        pass
                    except Exception as e:
                        _logger.error(
                            f"Error processing GPS data for {self.device_identifier}: {e}"
                        )

                # Small delay to prevent CPU spinning
                self._stopped.wait(0.1)

            except Exception as e:
                _logger.error(f"GPS driver error for {self.device_identifier}: {e}")
                self._stopped.wait(1)  # Wait longer on error

        _logger.info(f"GPS Network Driver thread stopped for {self.device_identifier}")

    def disconnect(self):
        """Clean up when disconnecting the device"""
        _logger.info(f"Disconnecting GPS device {self.device_identifier}")

        # Clear any remaining data
        self._clear_queue()

        # Call parent disconnect
        super().disconnect()
