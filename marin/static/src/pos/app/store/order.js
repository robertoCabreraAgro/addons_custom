/** @odoo-module */

import {Order} from "@point_of_sale/app/store/models";
import {patch} from "@web/core/utils/patch";
import {MissingStockPopup} from "@marin/pos/app/popups/missing_stock_popup/missing_stock_popup";
import {_t} from "@web/core/l10n/translation";

patch(Order.prototype, {
    wait_for_push_order() {
        return true;
    },
    getTrackingLines() {
        const trackingLines = this.get_orderlines().filter((line) => line.has_product_lot);
        return trackingLines;
    },
    /**
     * Validates each order line with a lot and returns the quantity needed to complete the
     * order line. In case there is no stock left for the current lot, a number
     * will indicate the missing quantity.
     *
     * @returns {Array<Number>} The quantity needed to complete the order line.
     */
    async getMissingInventory(orderlines) {
        const orderlinesData = orderlines.flatMap((line) => {
            return [
                {
                    product_id: line.product.id,
                    quantity: line.quantity,
                    lot: line.pack_lot_lines.length ? line.pack_lot_lines[0].lot_name : false,
                },
            ];
        });
        const missing_inventory = await this.pos.orm.call("pos.config", "validate_stock_on_pos_order", [
            this.pos.config.id,
            orderlinesData,
        ]);
        return missing_inventory;
    },
    async setMissingQtyOnLines() {
        const missing_inventory = await this.getMissingInventory(this.get_orderlines());
        this.get_orderlines().forEach((track_line, idx) => {
            track_line.stock_lot_qty_missing = missing_inventory[idx];
        });
    },
    async pay() {
        if (!this.orderlines.length) {
            return;
        }
        await this.setMissingQtyOnLines();
        const missing_inventory = this.get_orderlines().map((line) => line.stock_lot_qty_missing);
        if (missing_inventory.some((missing_qty) => missing_qty)) {
            await this.pos.env.services.popup.add(MissingStockPopup, {
                order_lines: this.get_orderlines(),
                order: this,
                title: _t("Missing inventory for these serials number"),
                caption: _t("Choose a lot for this orderline"),
            });
            return false;
        }
        this.pos.mobile_pane = "right";
        this.env.services.pos.showScreen("PaymentScreen");
    },
});
