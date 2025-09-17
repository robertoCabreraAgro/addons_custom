
import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { _t } from "@web/core/l10n/translation";

patch(ProductScreen.prototype, {
    async addProductToOrder(product) {
        // Only storable products
        if (product && product.is_storable && this.pos.config.show_product_forecast) {
            // Get forecasted info
            const info = await this.pos.getProductInfo(product, 1);
            let forecastedQty = 0;
            if (info && info.productInfo && info.productInfo.warehouses) {
                // Sum forecast from all warehouses (adjust if you use different logic)
                forecastedQty = info.productInfo.warehouses.reduce((sum, w) => sum + (w.forecasted_quantity || 0), 0);
            }
            if (forecastedQty <= 0) {
                this.notification.add(_t("You cannot add this product because the forecast is 0."), { type: "danger" });
                return;
            }
        }
        // If validation passes, continue normal flow
        await super.addProductToOrder(product);
    },
});
