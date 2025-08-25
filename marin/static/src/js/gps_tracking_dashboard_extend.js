/** @odoo-module **/

import { GpsTrackingDashboard } from "@gps_tracking/js/gps_tracking_dashboard";
import { patch } from "@web/core/utils/patch";

// Extend GpsTrackingDashboard to include driver_name and department_id fields
patch(GpsTrackingDashboard.prototype, {
    
    async _reloadDevicesWithDomain(domain) {
        try {
            const devices = await this.orm.searchRead(
                "gps.tracking.device",
                domain || [],
                ["id", "imei", "the_point", "speed", "timestamp", "altitude", "satellite", "address", "gsm_signal", "ignition", "movement", "color", "vehicle_id", "license_plate", "driver_name", "odometer", "department_id", "location"]
            );
            this.state.devices = devices;
            this.state.filteredDevices = devices;
        } catch (error) {
            console.error("Error loading devices:", error);
        }
    },

    async loadDevices() {
        try {
            const devices = await this.orm.searchRead(
                "gps.tracking.device",
                [],
                ["id", "imei", "the_point", "speed", "timestamp", "altitude", "satellite", "address", "gsm_signal", "ignition", "movement", "color", "vehicle_id", "license_plate", "driver_name", "odometer", "department_id", "location"]
            );
            this.state.devices = devices;
        } catch (error) {
            console.error("Error loading devices:", error);
            this.state.devices = [];
        }
    }
});