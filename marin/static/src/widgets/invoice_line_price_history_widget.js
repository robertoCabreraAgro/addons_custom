/** @odoo-module **/

import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

const {Component} = owl;

export class InvoicePriceHistoryWidget extends Component {
    setup() {
        super.setup();
        this.actionService = useService("action");
    }

    async viewInvoicePriceHistory() {
        this.actionService.doAction("marin.invoice_line_price_history_action", {
            additionalContext: {
                default_line_id: this.props.record.data.id,
                default_partner_id: this.props.record.data.partner_id[0],
                default_product_id: this.props.record.data.product_id[0],
            },
        });
    }
}

InvoicePriceHistoryWidget.template = "InvoicePriceHistory";

registry.category("view_widgets").add("invoice_line_price_history_widget", {component: InvoicePriceHistoryWidget});
