import { Component, useState, onMounted } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";

export class GeofenceDialog extends Component {
    static template = "gps_tracking.geofence_dialog";
    static components = { Dialog };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            partners: [],
            geofences: [],
            form: {
                name: "",
                area_type: "property",
                partner_id: "",
                parent_id: "",
                color: "#ff0000",
                sequence: 10,
                description: "",
            },
        });

        onMounted(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        /**
         * Load partners and existing geofences for the selects
         */
        try {
            // Load partners (clients)
            const partners = await this.orm.searchRead(
                "res.partner",
                [["is_company", "=", true]],
                ["id", "name"]
            );

            // Load existing geofences for parent selection
            const geofences = await this.orm.searchRead(
                "gps.geofence",
                [["active", "=", true]],
                ["id", "name", "area_type"]
            );

            this.state.partners = partners;
            this.state.geofences = geofences;
        } catch (error) {
            console.error("Error loading modal data:", error);
        }
    }


    async onSave() {
        /**
         * Save the geofence with form data
         */
        const { name, area_type } = this.state.form;
        
        // Validate required fields
        if (!name || !area_type) {
            alert("Please fill in all required fields (Name and Area Type).");
            return;
        }

        if (!this.props.geometry) {
            alert("Please draw a geographic area first.");
            return;
        }

        try {
            const geofenceData = {
                name: this.state.form.name,
                geometry: this.props.geometry,
                color: this.state.form.color,
                area_type: this.state.form.area_type,
                partner_id: this.state.form.partner_id ? parseInt(this.state.form.partner_id) : false,
                parent_id: this.state.form.parent_id ? parseInt(this.state.form.parent_id) : false,
                sequence: parseInt(this.state.form.sequence) || 10,
                description: this.state.form.description,
                active: true,
            };

            // Save the geofence in Odoo
            const result = await this.orm.create("gps.geofence", [geofenceData]);
            console.log("Geographic area saved in Odoo:", result);

            // Call the success callback
            if (this.props.onSave) {
                this.props.onSave(result);
            }

            // Close dialog
            this.props.close();

        } catch (error) {
            console.error("Error saving geographic area in Odoo:", error);
            alert("There was an error saving the geographic area.");
        }
    }

    onCancel() {
        /**
         * Cancel and close dialog
         */
        this.props.close();
    }
}