/** @odoo-module */

import {ReceiptScreen} from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import {onMounted, useState} from "@odoo/owl";
import {patch} from "@web/core/utils/patch";

patch(ReceiptScreen.prototype, {
    setup() {
        super.setup();
        this.state = useState({
            delivery_info_array: null,
        });
        onMounted(async () => {
            this.state.delivery_info_array = await this.orm.call("pos.order", "get_delivery_info", [
                this.currentOrder.server_id,
            ]);
        });
    },
});
