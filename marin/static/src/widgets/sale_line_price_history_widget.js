/** @odoo-module **/

import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

const {Component} = owl;

export class SalePriceHistoryWidget extends Component {
    setup() {
        super.setup();
        this.actionService = useService("action");
    }

    async viewSalePriceHistory() {
        this.actionService.doAction("marin.sale_line_price_history_action", {
            additionalContext: {
                default_line_id: this.props.record.data.id,
                default_partner_id: this.props.record.data.order_partner_id[0],
                default_product_id: this.props.record.data.product_id[0],
            },
        });
    }
}

SalePriceHistoryWidget.template = "SalePriceHistory";

registry.category("view_widgets").add("sale_line_price_history_widget", {component: SalePriceHistoryWidget});
