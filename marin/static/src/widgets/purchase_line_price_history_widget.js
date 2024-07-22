/** @odoo-module **/

import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

const {Component} = owl;

export class PurchasePriceHistoryWidget extends Component {
    setup() {
        super.setup();
        this.actionService = useService("action");
    }

    async viewPurchasePriceHistory() {
        this.actionService.doAction("marin.purchase_line_price_history_action", {
            additionalContext: {
                default_line_id: this.props.record.data.id,
                default_partner_id: this.props.record.data.partner_id[0],
                default_product_id: this.props.record.data.product_id[0],
            },
        });
    }
}

PurchasePriceHistoryWidget.template = "PurchasePriceHistory";

registry.category("view_widgets").add("purchase_line_price_history_widget", {component: PurchasePriceHistoryWidget});
