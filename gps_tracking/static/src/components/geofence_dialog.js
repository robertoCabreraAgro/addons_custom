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
      filteredPartners: [],
      geofences: [],
      geofenceTypes: [],
      form: {
        name: "",
        area_type: "",
        partner_id: "",
        partner_name: "",
        parent_id: "",
        color: "#ff0000",
        sequence: 10,
        description: "",
        surface: 0,
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
      // Load partners (clients only, not suppliers)
      const partners = await this.orm.searchRead(
        "res.partner",
        [
          "|",
          ["customer_rank", ">", 0],
          ["customer", "=", true]
        ],
        ["id", "name"]
      );

      // Load existing geofences for parent selection
      const geofences = await this.orm.searchRead(
        "gps.geofence",
        [["active", "=", true]],
        ["id", "name", "area_type"]
      );

      // Load geofence types for color/sequence computation
      const geofenceTypes = await this.orm.searchRead(
        "gps.geofence.type",
        [["active", "=", true]],
        ["id", "name", "code", "color", "sequence"]
      );

      // Filter out partners with invalid names
      const validPartners = partners.filter(
        (partner) => partner && partner.name
      );
      this.state.partners = validPartners;
      this.state.filteredPartners = validPartners;
      this.state.geofences = geofences;
      this.state.geofenceTypes = geofenceTypes;

      // Set default area_type to first available type
      if (geofenceTypes.length > 0) {
        this.state.form.area_type = geofenceTypes[0].code;
      }

      // Set initial color/sequence based on default area_type
      this.updateColorSequence();

      // Now that data is loaded and area_type is set, detect container
      await this.detectContainerAndPrePopulate();
    } catch (error) {
      console.error("Error loading modal data:", error);
    }
  }

  updateColorSequence() {
    /**
     * Update color and sequence based on selected area_type
     */
    const selectedType = this.state.geofenceTypes.find(
      (type) => type.code === this.state.form.area_type
    );

    if (selectedType) {
      this.state.form.color = selectedType.color;
      this.state.form.sequence = selectedType.sequence;
    }
  }

  onAreaTypeChange(event) {
    /**
     * Handle area type change and update color/sequence
     */
    this.state.form.area_type = event.target.value;
    this.updateColorSequence();
  }


  onPartnerSearch(event) {
    /**
     * Filter partners based on search input
     */
    const searchTerm = event.target.value.toLowerCase();
    if (searchTerm) {
      this.state.filteredPartners = this.state.partners.filter(
        (partner) =>
          partner &&
          partner.name &&
          partner.name.toLowerCase().includes(searchTerm)
      );
    } else {
      this.state.filteredPartners = this.state.partners;
    }
  }

  onPartnerBlur(event) {
    /**
     * Handle partner selection when user selects from datalist
     */
    const selectedName = event.target.value;
    const selectedPartner = this.state.partners.find(
      (partner) => partner && partner.name && partner.name === selectedName
    );

    if (selectedPartner) {
      this.state.form.partner_id = selectedPartner.id;
      this.state.form.partner_name = selectedPartner.name;
    } else {
      this.state.form.partner_id = "";
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
      // Ensure geometry is a JSON string for consistency
      const geometryJson =
        typeof this.props.geometry === "string"
          ? this.props.geometry
          : JSON.stringify(this.props.geometry);

      // Detect container before saving
      const containerInfo = await this.orm.call(
        "gps.geofence",
        "find_container_for_geometry",
        [geometryJson, area_type]
      );

      // Check for validation errors
      if (
        containerInfo.validation_errors &&
        containerInfo.validation_errors.length > 0
      ) {
        const errorMessage = containerInfo.validation_errors.join("\n");
        alert(`Validation errors:\n${errorMessage}`);
        return;
      }

      const geofenceData = {
        name: this.state.form.name,
        geometry: geometryJson,
        color: this.state.form.color,
        area_type: this.state.form.area_type,
        partner_id: this.state.form.partner_id
          ? parseInt(this.state.form.partner_id)
          : false,
        parent_id: this.state.form.parent_id
          ? parseInt(this.state.form.parent_id)
          : false,
        sequence: parseInt(this.state.form.sequence) || 10,
        description: this.state.form.description,
        active: true,
      };

      // Pre-populate inherited fields if container was found
      if (containerInfo.parent_id) {
        geofenceData.parent_id = containerInfo.parent_id;

        // Only inherit partner_id if not manually set
        if (!this.state.form.partner_id && containerInfo.partner_id) {
          geofenceData.partner_id = containerInfo.partner_id;
        }
      }

      // Save the geofence in Odoo
      const result = await this.orm.create("gps.geofence", [geofenceData]);

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

  async detectContainerAndPrePopulate() {
    /**
     * Detect container geofence and pre-populate form fields
     */
    if (!this.props.geometry) {
      return;
    }

    try {
      // Calculate surface area first
      const surfaceArea = await this.calculateSurfaceArea();
      this.state.form.surface = surfaceArea;

      // Get area type from form (should be set by now)
      const areaType = this.state.form.area_type || "property";

      // Ensure geometry is a JSON string
      const geometryJson =
        typeof this.props.geometry === "string"
          ? this.props.geometry
          : JSON.stringify(this.props.geometry);

      // Detect container
      const containerInfo = await this.orm.call(
        "gps.geofence",
        "find_container_for_geometry",
        [geometryJson, areaType]
      );


      // Show validation errors if any (non-blocking)
      if (
        containerInfo.validation_errors &&
        containerInfo.validation_errors.length > 0
      ) {
        // Don't return here, continue with pre-population if parent was found
      }

      // Pre-populate fields if container found
      if (containerInfo.parent_id) {

        // Get parent geofence details
        const parentGeofence = await this.orm.searchRead(
          "gps.geofence",
          [["id", "=", containerInfo.parent_id]],
          ["id", "name", "partner_id", "area_type"]
        );

        if (parentGeofence && parentGeofence.length > 0) {
          const parent = parentGeofence[0];

          // Set parent_id
          this.state.form.parent_id = parent.id.toString();

          // Pre-populate partner only if not manually set
          if (!this.state.form.partner_id && containerInfo.partner_id) {
            this.state.form.partner_id = containerInfo.partner_id.toString();

            // Find partner name for display
            const partner = this.state.partners.find(
              (p) => p.id === containerInfo.partner_id
            );
            if (partner) {
              this.state.form.partner_name = partner.name;
            }
          }
        }
      }
    } catch (error) {
      console.error("Error detecting container:", error);
      // Don't block the dialog from opening, just log the error
    }
  }

  async calculateSurfaceArea() {
    /**
     * Calculate surface area of the geometry using PostGIS
     */
    if (!this.props.geometry) {
      return 0;
    }

    try {
      // Ensure geometry is a JSON string
      const geometryJson =
        typeof this.props.geometry === "string"
          ? this.props.geometry
          : JSON.stringify(this.props.geometry);

      // Use a temporary method to calculate surface
      const result = await this.orm.call(
        "gps.geofence",
        "calculate_geometry_surface",
        [geometryJson]
      );
      return parseFloat((result || 0).toFixed(4));
    } catch (error) {
      console.warn("Error calculating surface area:", error);
      return 0;
    }
  }

  onCancel() {
    /**
     * Cancel and close dialog
     */
    this.props.close();
  }
}
