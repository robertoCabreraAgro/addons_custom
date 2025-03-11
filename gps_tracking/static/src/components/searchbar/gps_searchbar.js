/** @odoo-module **/

import { Component, useRef } from "@odoo/owl";

export class GpsSearchbar extends Component {
    static template = "gps_tracking.GpsSearchbar";
    static props = {
        initialQuery: { type: String, optional: true }, // Opcional
        onSearch: { type: Function }, // Requerido
    };

    setup() {
        this.searchInput = useRef("searchInput");

        if (this.props.initialQuery) {
            this.searchInput.el.value = this.props.initialQuery;
        }
    }

    triggerSearch() {
        const query = this.searchInput.el.value.trim();
        if (this.props.onSearch) {
            this.props.onSearch(query); // Llama a la función pasada como prop
        }
    }
}