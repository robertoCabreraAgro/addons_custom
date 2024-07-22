/** @odoo-module */

import {PosStore} from "@point_of_sale/app/store/pos_store";
import {patch} from "@web/core/utils/patch";

patch(PosStore.prototype, {
    /**
     * Function overrided to replae the company_id parameter sent to the backend.
     * We changed this.env.session.company_id (single company)
     * to this.env.session.user_companies.current_company (multi company)
     */
    async getProductLots(product) {
        try {
            return await this.orm.call("stock.lot", "get_available_lots_for_pos", [
                product.id,
                this.company.id,
                this.config.id,
            ]);
        } catch (error) {
            console.error(error);
            return [];
        }
    },
});
