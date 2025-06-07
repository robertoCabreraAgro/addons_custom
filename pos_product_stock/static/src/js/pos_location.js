/** @odoo-module */
import {ProductCard} from "@point_of_sale/app/components/product_card/product_card";
import {usePos} from "@point_of_sale/app/hooks/pos_hook";
import {patch} from "@web/core/utils/patch";
import {useService} from "@web/core/utils/hooks";
import {useRef, useState} from "@odoo/owl";
patch(ProductCard.prototype, {
    setup() {
        super.setup();
        this.pos = usePos();
        this.orm = useService("orm");
        this.state = useState({
            qty_available: null,
            incoming_qty: null,
            outgoing_qty: null,
            display_stock: false,
        });
    },
    async fetchProductDetails(productId) {
        const product = await this.orm.call("product.template", "read", [
            [productId],
            ["name", "id", "incoming_qty", "outgoing_qty", "qty_available"],
        ]);
        return product[0];
    },
    async updateProductDetails() {
        const productId = this.props.productId;
        if (productId) {
            this.productDetail = await this.fetchProductDetails(productId);
        }
    },
    get value() {
        if (this.pos.config.display_stock_setting == true) {
            const current_product = this.props.productId;
            const current_product_name = this.props.name;
            const move_line = this.pos.move_line;
            const stock_product = this.pos.stock_quant;
            const product_product = this.pos.product_product;
            let qty = 0;
            let on_hand = 0;
            let outgoing = 0;
            let incoming = 0;
            const product_variants = product_product.filter(
                (product) => product.raw.product_tmpl_id === current_product
            );
            if (this.pos.config.raw.pos_stock_location_id) {
                stock_product.forEach((product) => {
                    if (product && product.product_id) {
                        if (
                            product.raw.location_id == this.pos.config.raw.pos_stock_location_id ||
                            this.pos.config.pos_stock_location_id.child_ids.some(
                                (location) => location.id === product.raw.location_id
                            )
                        ) {
                            const is_variant = product_variants.some(
                                (variant) => variant.id === product.product_id.id
                            );
                            if (is_variant) {
                                qty += product.available_quantity;
                                on_hand += product.quantity;
                            }
                        }
                    }
                });
                move_line.forEach((line) => {
                    if (line && line.product_id) {
                        if (
                            line.product_id.product_tmpl_id == current_product &&
                            this.pos.config.raw.pos_stock_location_id == line.raw.location_dest_id
                        ) {
                            incoming += line.product_id.incoming_qty;
                        }
                        if (
                            line.product_id.product_tmpl_id == current_product &&
                            this.pos.config.raw.pos_stock_location_id == line.raw.location_id
                        ) {
                            outgoing += line.product_id.outgoing_qty;
                        }
                    }
                });
            }

            if (!this.props.available) {
                this.props.available = qty;
            }
            if (!this.props.on_hand) {
                this.props.on_hand = on_hand;
            }
            if (!this.props.outgoing) {
                this.props.outgoing = outgoing;
            }
            if (!this.props.incoming) {
                this.props.incoming_loc = incoming;
            }

            this.updateProductDetails().then(() => {
                this.state.qty_available = this.productDetail.qty_available;
                this.state.incoming_qty = this.productDetail.incoming_qty;
                this.state.outgoing_qty = this.productDetail.outgoing_qty;
            });
            this.state.display_stock = true;
            return {
                display_stock: this.pos.config.display_stock_setting,
            };
        } else {
            return {
                display_stock: false,
            };
        }
    },
});
