/** @odoo-module */

import {PaymentScreen} from "@point_of_sale/app/screens/payment_screen/payment_screen";
import {patch} from "@web/core/utils/patch";
import {_t} from "@web/core/l10n/translation";
import {MissingStockPopup} from "@marin/pos/app/popups/missing_stock_popup/missing_stock_popup";

patch(PaymentScreen.prototype, {
    async _isOrderValid(isForceValidate) {
        await this.currentOrder.setMissingQtyOnLines();
        const missing_inventory = this.currentOrder.get_orderlines().map((line) => line.stock_lot_qty_missing);
        if (missing_inventory.some((missing_qty) => missing_qty)) {
            await this.env.services.popup.add(MissingStockPopup, {
                order_lines: this.currentOrder.get_orderlines(),
                order: this.currentOrder,
                title: _t("Missing inventory for these serials number"),
                caption: _t("Choose a lot for this orderline"),
            });
            return false;
        }
        return super._isOrderValid(isForceValidate);
    },
    /**
     * We need the server ID within the same PoS page, so we assign it after the forced push.
     * @returns {Boolean} If falsy, the payment screen will not be closed.
     */
    async _postPushOrderResolve(order, order_server_ids) {
        if (order_server_ids.length) {
            order.server_id = order_server_ids[0];
        }
        return await super._postPushOrderResolve(...arguments);
    },
});
