/** @odoo-module */
import {patch} from "@web/core/utils/patch";
import {PosStore} from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    async processServerData(data) {
        super.processServerData(...arguments);
        this.stock_quant = this.models["stock.quant"].getAll();
        this.move_line = this.models["stock.move.line"].getAll();
        this.product_product = this.models["product.product"].getAll();
    },
});
