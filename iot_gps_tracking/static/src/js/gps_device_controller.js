/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class GPSDeviceController extends Component {
    static template = "iot_gps_tracking.GPSDeviceController";
    static props = {
        device: Object,
        onPositionUpdate: { type: Function, optional: true },
    };

    setup() {
        this.rpc = useService("rpc");
        this.notification = useService("notification");
        this.action = useService("action");
    }

    async startTracking() {
        try {
            const result = await this.rpc("/web/dataset/call_kw/iot.device/action_start_tracking", {
                model: "iot.device",
                method: "action_start_tracking",
                args: [[this.props.device.id]],
                kwargs: {},
            });
            
            this.notification.add("Tracking started", {
                type: "success",
            });
            
            if (this.props.onPositionUpdate) {
                this.props.onPositionUpdate(this.props.device.id);
            }
        } catch (error) {
            this.notification.add("Failed to start tracking", {
                type: "danger",
            });
        }
    }

    async stopTracking() {
        try {
            const result = await this.rpc("/web/dataset/call_kw/iot.device/action_stop_tracking", {
                model: "iot.device",
                method: "action_stop_tracking",
                args: [[this.props.device.id]],
                kwargs: {},
            });
            
            this.notification.add("Tracking stopped", {
                type: "info",
            });
            
            if (this.props.onPositionUpdate) {
                this.props.onPositionUpdate(this.props.device.id);
            }
        } catch (error) {
            this.notification.add("Failed to stop tracking", {
                type: "danger",
            });
        }
    }

    async getCurrentPosition() {
        try {
            const result = await this.rpc("/web/dataset/call_kw/iot.device/action_get_current_position", {
                model: "iot.device",
                method: "action_get_current_position",
                args: [[this.props.device.id]],
                kwargs: {},
            });
            
            this.notification.add("Position request sent", {
                type: "info",
            });
        } catch (error) {
            this.notification.add("Failed to get position", {
                type: "danger",
            });
        }
    }

    async viewOnMap() {
        if (!this.props.device.gps_last_latitude || !this.props.device.gps_last_longitude) {
            this.notification.add("No GPS position available", {
                type: "warning",
            });
            return;
        }

        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Device Location",
            res_model: "iot.device",
            view_mode: "map",
            views: [[false, "map"]],
            domain: [["id", "=", this.props.device.id]],
            context: {
                map_center_lat: this.props.device.gps_last_latitude,
                map_center_lng: this.props.device.gps_last_longitude,
                map_zoom: 15,
            },
        });
    }

    async viewTrackingHistory() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Tracking History",
            res_model: "iot.gps.tracking.point",
            view_mode: "list,form,map,graph",
            domain: [["iot_device_id", "=", this.props.device.id]],
            context: {
                default_iot_device_id: this.props.device.id,
                search_default_last_week: 1,
            },
        });
    }
}

registry.category("components").add("GPSDeviceController", GPSDeviceController);