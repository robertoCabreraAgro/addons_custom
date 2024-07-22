/** @odoo-module */

import {Orderline} from "@point_of_sale/app/store/models";
import {patch} from "@web/core/utils/patch";
import {_t} from "@web/core/l10n/translation";
import {MissingStockPopup} from "@marin/pos/app/popups/missing_stock_popup/missing_stock_popup";

patch(Orderline.prototype, {
    async editPackLotLines() {
        await this.order.setMissingQtyOnLines();
        await this.env.services.popup.add(MissingStockPopup, {
            order_lines: [this],
            order: this.order,
            title: _t("Edit Lot/Serial Number"),
            caption: _t("Choose a lot for this orderline"),
        });
    },
    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        json.stock_lot_qty_missing = this.stock_lot_qty_missing;
        return json;
    },
    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.stock_lot_qty_missing = json.stock_lot_qty_missing;
    },
    clone() {
        const cloned = super.clone(...arguments);
        cloned.stock_lot_qty_missing = this.stock_lot_qty_missing;
        return cloned;
    },
});
