/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { WithSearch } from "@web/search/with_search/with_search";
import { GpsTrackingTimeline } from "../../js/gps_tracking_timeline";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { Component, onWillStart } from "@odoo/owl";
import { GpsSearchModel } from "./gps_search_model";  // (Opcional, ver paso 2)
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { SearchBar } from "@web/search/search_bar/search_bar";



export class GpsTrackingActionTimeline extends Component {
    static template = "gps_tracking.gps_tracking_action_timeline"; // (la vista XML que haremos en el paso 3)
    static components = { WithSearch, GpsTrackingTimeline, ControlPanel, SearchBar};
    static props = { ...standardActionServiceProps };

    setup() {
        this.viewService = useService("view");
        this.resModel = "gps.tracking.device";

        onWillStart(async () => {
            // 1) Cargar la vista de búsqueda
            const views = await this.viewService.loadViews({
                resModel: this.resModel,
                context: this.props.action.context,
                views: [[false, "search"]],
            });

            // 2) Configuramos las propiedades para WithSearch
            this.withSearchProps = {
                resModel: this.resModel,
                SearchModel: GpsSearchModel,  // (o SearchModel si no necesitas personalizar)
                context: this.props.action.context,
                domain: this.props.action.domain || [],
                orderBy: [{ name: "id", asc: true }],
                searchMenuTypes: ["filter", "groupBy", "favorite"], 
                searchViewArch: views.views.search.arch,
                searchViewId: views.views.search.id,
                searchViewFields: views.fields,
                loadIrFilters: true,
            };
        });
    }
}

// Registra la acción para usarla en tu XML/menú
registry.category("actions").add("gps_tracking_client_action_timeline", GpsTrackingActionTimeline);