/** @odoo-module **/

import { GpsTrackingDashboard } from "@gps_tracking/js/gps_tracking_dashboard";
import { patch } from "@web/core/utils/patch";

// Extend GpsTrackingDashboard to include department_id field
patch(GpsTrackingDashboard.prototype, {
    
    async _reloadDevicesWithDomain(domain) {
        console.log("Recargando con domain:", domain);
        // Llama a searchRead en gps.tracking.device con ese domain
        try {
            const devices = await this.orm.searchRead(
                "gps.tracking.device",
                domain || [],
                ["id", "imei", "the_point", "speed", "timestamp", "altitude", "satellite", "address", "gsm_signal", "ignition", "movement", "color", "vehicle_id", "license_plate", "driver_name", "odometer", "department_id", "location"]
            );
            this.state.devices = devices;
            this.state.filteredDevices = devices;
            // Actualizar marcadores si lo deseas, etc.
        } catch (error) {
            console.error("Error al recargar dispositivos:", error);
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
            console.error("Error al cargar los dispositivos:", error);
            this.state.devices = [];
        }
    }
});