/**
 * Patch to ProductCard for displaying a forecast card with predicted quantity in POS products.
 * Handles warehouse selection logic, placeholder for all warehouses, and visual feedback.
 */

import { ProductCard } from "@point_of_sale/app/components/product_card/product_card";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { useState, useEffect, onWillUnmount } from "@odoo/owl";
import { useTrackedAsync } from "@point_of_sale/app/hooks/hooks";
import { debounce } from "@web/core/utils/timing";

import { ConfirmAndPropagate } from "./product_confirm_patch";
import { patch } from "@web/core/utils/patch";

patch(ProductCard.prototype, {
    ConfirmAndPropagate,

    setup() {
        super.setup();
        this.pos = usePos();

        // Patch: Interceptar el click original para usar la cantidad personalizada
        const originalOnClick = this.props.onClick;
        this.props.onClick = async (ev) => {
            // Detectar popup OWL solo si está disponible en this.env.services.popup
            const popup = this.env && this.env.services && this.env.services.popup ? this.env.services.popup : null;
            // Obtener almacenes genéricos del loader (si existen en this.pos)
            let almacenesGenericos = [];
            if (this.pos && this.pos.warehouses) {
                almacenesGenericos = this.pos.warehouses.map(w => ({
                    id: w.id,
                    name: w.display_name || w.name
                }));
            }
            // Obtener forecast de almacenes del producto
            let almacenes = [];
            let forecastById = {};
            let warehousesForecast = [];
            if (this.fetchProductInfo) {
                try {
                    await this.fetchProductInfo.call(this.props.product);
                    if (this.fetchProductInfo.status === "success") {
                        const result = this.fetchProductInfo.result;
                        if (result && result.productInfo && Array.isArray(result.productInfo.warehouses)) {
                            warehousesForecast = result.productInfo.warehouses;
                            // Mapear forecast por id
                            forecastById = Object.fromEntries(warehousesForecast.map(w => [w.id, w.forecasted_quantity]));
                        }
                    }
                } catch (e) {
                    console.warn("No se pudo obtener forecast de almacenes para el modal", e);
                }
            }
            // DEBUG: Log both arrays before merging
            console.log('[DEBUG] almacenesGenericos:', almacenesGenericos);
            console.log('[DEBUG] warehousesForecast:', warehousesForecast);

            // If almacenesGenericos is empty, use warehousesForecast directly
            if (almacenesGenericos && almacenesGenericos.length) {
                almacenes = almacenesGenericos.map(w => ({
                    ...w,
                    forecasted_quantity: forecastById[w.id] !== undefined ? forecastById[w.id] : undefined
                }));
            } else {
                almacenes = warehousesForecast.map(w => ({
                    id: w.id,
                    name: w.display_name || w.name || w.id,
                    forecasted_quantity: w.forecasted_quantity
                }));
            }
            // DEBUG: Log almacenes after merge/fallback
            console.log('[DEBUG] almacenes to modal:', almacenes);
            // Pasar almacenes como prop extra al modal
            this.ConfirmAndPropagate.call(this, ev, popup, originalOnClick, almacenes);
        };

        // ...existing code...

        // State to store forecast info
        this.forecastState = useState({
            forecastedQty: 0,
            isLoading: false,
            isVisible: false,
        });

        // Function to get forecast data
        this.fetchProductInfo = useTrackedAsync((product) => {
            return this.pos.getProductInfo(product, 1);
        }, { keepLast: true });

        // Debounced function to get forecast
        const debouncedFetchForecast = debounce(async (product) => {
            // Check if forecast is enabled
            if (!this.pos.config.show_product_forecast || !product || !product.is_storable) {
                this.forecastState.isVisible = false;
                return;
            }

            this.forecastState.isLoading = true;

            try {
                await this.fetchProductInfo.call(product);

                if (this.fetchProductInfo.status === "success") {
                    const result = this.fetchProductInfo.result;
                    if (result && result.productInfo && result.productInfo.warehouses) {
                        const totalForecastedQty = this.calculateForecastedQty(result.productInfo.warehouses);

                        this.forecastState.forecastedQty = totalForecastedQty;
                        this.forecastState.isVisible = true;
                    }
                }
            } catch (error) {
                console.warn("Error fetching product forecast:", error);
                this.forecastState.isVisible = false;
            } finally {
                this.forecastState.isLoading = false;
            }
        }, 300);

        // Effect to load data when product changes
        useEffect(
            () => {
                if (this.props.product) {
                    debouncedFetchForecast(this.props.product);
                }
            },
            () => [this.props.product?.id]
        );

        onWillUnmount(() => debouncedFetchForecast.cancel());
    },

    calculateForecastedQty(warehouses) {
        if (!warehouses || !Array.isArray(warehouses)) {
            return 0;
        }

        // Total sum of all warehouses
        const warehouseIds = warehouses.map(w => Number(w.id));
        const totalAllWarehouses = warehouses.reduce((sum, warehouse) => sum + (warehouse.forecasted_quantity || 0), 0);

        // If no indexes selected, sum all warehouses (placeholder: All Warehouses)
        const indexString = this.pos.config.forecast_warehouse_indexes;
        let selectedIndexes = [];
        if (indexString && typeof indexString === 'string') {
            selectedIndexes = indexString.split(',').map(s => parseInt(s.trim(), 10)).filter(n => !isNaN(n));
        }
        if (selectedIndexes.length > 0) {
            // Warn if any index is out of range
            const outOfRange = selectedIndexes.filter(idx => idx < 0 || idx >= warehouses.length);
            if (outOfRange.length > 0) {
                // Example of internationalization for warning
                // eslint-disable-next-line no-undef
                if (typeof _t !== 'undefined') {
                    console.warn(_t("Some warehouse indexes are out of range: %s").replace('%s', outOfRange.join(', ')));
                } else {
                    console.warn("Some warehouse indexes are out of range:", outOfRange.join(', '));
                }
            }
            const selectedWarehousesByIndex = selectedIndexes.map(idx => warehouses[idx]).filter(w => w);
            const selectedSumByIndex = selectedWarehousesByIndex.reduce((sum, w) => sum + (w.forecasted_quantity || 0), 0);
            return selectedSumByIndex;
        }
        // If no indexes, sum all
        return totalAllWarehouses;
    },

    get shouldShowForecastCard() {
        return this.pos.config.show_product_forecast &&
               this.forecastState.isVisible && 
               this.props.product?.is_storable && 
               !this.forecastState.isLoading;
    },


    get forecastQtyDisplay() {
        const qty = this.forecastState.forecastedQty;
        if (qty === 0) return "0";
        if (qty < 1000) return String(qty);
        if (qty < 1000000) return (qty / 1000).toFixed(1) + "K";
        return (qty / 1000000).toFixed(1) + "M";
    },

    get forecastCardClass() {
        const qty = this.forecastState.forecastedQty;
        if (qty <= 0) return "forecast-danger";
        if (qty <= 10) return "forecast-warning";
        return "forecast-success";
    }
});
