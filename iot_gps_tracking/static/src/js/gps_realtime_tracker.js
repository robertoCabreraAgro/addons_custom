/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class GPSRealtimeTracker extends Component {
    static template = "iot_gps_tracking.GPSRealtimeTracker";
    static props = {
        deviceIds: Array,
        updateInterval: { type: Number, optional: true },
        onUpdate: { type: Function, optional: true },
    };

    setup() {
        this.rpc = useService("rpc");
        this.notification = useService("notification");
        this.busService = useService("bus_service");
        
        this.state = {
            devices: {},
            connected: false,
            lastUpdate: null,
        };
        
        this.updateInterval = this.props.updateInterval || 30000; // 30 seconds default
        this.updateTimer = null;
        
        onWillStart(async () => {
            await this.loadDevices();
        });
        
        onMounted(() => {
            this.startTracking();
            this.subscribeToUpdates();
        });
        
        onWillUnmount(() => {
            this.stopTracking();
        });
    }

    async loadDevices() {
        try {
            const devices = await this.rpc("/web/dataset/search_read", {
                model: "iot.device",
                domain: [["id", "in", this.props.deviceIds]],
                fields: [
                    "name",
                    "gps_imei",
                    "gps_last_latitude",
                    "gps_last_longitude",
                    "gps_last_speed",
                    "gps_last_update",
                    "gps_tracking_enabled",
                    "connected_status",
                ],
            });
            
            devices.forEach(device => {
                this.state.devices[device.id] = device;
            });
        } catch (error) {
            console.error("Failed to load GPS devices:", error);
        }
    }

    subscribeToUpdates() {
        // Subscribe to bus notifications for GPS updates
        this.busService.subscribe("gps_position_update", (message) => {
            this.handlePositionUpdate(message);
        });
        
        this.busService.subscribe("gps_device_status", (message) => {
            this.handleStatusUpdate(message);
        });
    }

    handlePositionUpdate(message) {
        const { device_id, position } = message;
        
        if (this.state.devices[device_id]) {
            Object.assign(this.state.devices[device_id], {
                gps_last_latitude: position.latitude,
                gps_last_longitude: position.longitude,
                gps_last_speed: position.speed,
                gps_last_update: new Date().toISOString(),
            });
            
            this.state.lastUpdate = new Date();
            
            if (this.props.onUpdate) {
                this.props.onUpdate(device_id, position);
            }
            
            this.notification.add(`Position updated for ${this.state.devices[device_id].name}`, {
                type: "info",
                sticky: false,
            });
        }
    }

    handleStatusUpdate(message) {
        const { device_id, status } = message;
        
        if (this.state.devices[device_id]) {
            this.state.devices[device_id].connected_status = status;
            
            if (status === "disconnected") {
                this.notification.add(`Device ${this.state.devices[device_id].name} disconnected`, {
                    type: "warning",
                });
            }
        }
    }

    startTracking() {
        this.state.connected = true;
        
        // Set up periodic position updates
        this.updateTimer = setInterval(() => {
            this.requestPositionUpdates();
        }, this.updateInterval);
        
        // Request immediate update
        this.requestPositionUpdates();
    }

    stopTracking() {
        this.state.connected = false;
        
        if (this.updateTimer) {
            clearInterval(this.updateTimer);
            this.updateTimer = null;
        }
    }

    async requestPositionUpdates() {
        const deviceIds = Object.keys(this.state.devices).map(id => parseInt(id));
        
        try {
            await this.rpc("/web/dataset/call_kw/iot.device/action_get_current_position", {
                model: "iot.device",
                method: "action_get_current_position",
                args: [deviceIds],
                kwargs: {},
            });
        } catch (error) {
            console.error("Failed to request position updates:", error);
        }
    }

    getDeviceMarkers() {
        return Object.values(this.state.devices).map(device => ({
            id: device.id,
            name: device.name,
            position: {
                lat: device.gps_last_latitude,
                lng: device.gps_last_longitude,
            },
            speed: device.gps_last_speed,
            connected: device.connected_status === "connected",
            tracking: device.gps_tracking_enabled,
            lastUpdate: device.gps_last_update,
        }));
    }

    formatLastUpdate(device) {
        if (!device.gps_last_update) {
            return "Never";
        }
        
        const lastUpdate = new Date(device.gps_last_update);
        const now = new Date();
        const diffMs = now - lastUpdate;
        const diffMins = Math.floor(diffMs / 60000);
        
        if (diffMins < 1) {
            return "Just now";
        } else if (diffMins < 60) {
            return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
        } else {
            const diffHours = Math.floor(diffMins / 60);
            return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
        }
    }
}

registry.category("components").add("GPSRealtimeTracker", GPSRealtimeTracker);