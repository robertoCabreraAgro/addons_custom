/** @odoo-module */

import {ProductInfoPopup} from "@point_of_sale/app/screens/product_screen/product_info_popup/product_info_popup";
import {patch} from "@web/core/utils/patch";

patch(ProductInfoPopup.prototype, {
    _hasMarginsCostsAccessRights() {
        const isAccessibleToEveryUser = this.pos.config.is_margins_costs_accessible_to_every_user;
        const hasCostAccess = this.pos.get_cashier().cost_access == true;
        return isAccessibleToEveryUser || hasCostAccess;
    },
});
