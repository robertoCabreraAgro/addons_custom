/** @odoo-module **/
import {patch} from "@web/core/utils/patch";
import {useService} from "@web/core/utils/hooks";
import {AlertDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {ProductScreen} from "@point_of_sale/app/screens/product_screen/product_screen";
import {_t} from "@web/core/l10n/translation";

patch(ProductScreen.prototype, {
    setup() {
        super.setup();
    },
    async addProductToOrder(event) {
        const current_product_id = event.id;
        const product_product = this.pos.product_product;
        const stock_product = this.pos.stock_quant;
        const product_variants = product_product.filter(
            (product) => product.raw.product_tmpl_id === current_product_id
        );
        let total_qty_available = 0;
        if (this.pos.config.display_stock_setting) {
            if (this.pos.config.raw.pos_stock_location_id) {
                product_variants.forEach((variant) => {
                    stock_product.forEach((stock) => {
                        if (stock && stock.product_id) {
                            if (
                                stock.raw.location_id == this.pos.config.raw.pos_stock_location_id ||
                                this.pos.config.pos_stock_location_id.child_ids.some(
                                    (location) => location.id === stock.raw.location_id
                                )
                            ) {
                                if (stock.product_id.id == variant.id) {
                                    total_qty_available += stock.quantity;
                                }
                            }
                        }
                    });
                });
            }
            if (event.type === "consu") {
                if (this.pos.config["location_from"] === "all_warehouse") {
                    if (this.pos.config["stock_product"] === "on_hand") {
                        if (event.qty_available <= event.deny) {
                            await this.dialog.add(AlertDialog, {
                                title: _t("Deny Order"),
                                body: _t("%s is Out Of Stock", event.name),
                            });
                        } else {
                            super.addProductToOrder(event);
                        }
                    } else if (this.pos.config["stock_product"] === "outgoing_qty") {
                        if (event.outgoing_qty <= event.deny) {
                            await this.dialog.add(AlertDialog, {
                                title: _t("Deny Order"),
                                body: _t("%s is Out Of Stock", event.name),
                            });
                        } else {
                            super.addProductToOrder(event);
                        }
                    } else if (this.pos.config["stock_product"] === "incoming_qty") {
                        if (event.incoming_qty <= event.deny) {
                            await this.dialog.add(AlertDialog, {
                                title: _t("Deny Order"),
                                body: _t("%s is Out Of Stock", event.name),
                            });
                        } else {
                            super.addProductToOrder(event);
                        }
                    }
                } else if (this.pos.config["location_from"] === "current_warehouse") {
                    if (this.pos.config["stock_product"] === "on_hand") {
                        if (total_qty_available <= event.deny) {
                            await this.dialog.add(AlertDialog, {
                                title: _t("Deny Order"),
                                body: _t("%s is Out Of Stock", event.name),
                            });
                        } else {
                            super.addProductToOrder(event);
                        }
                    } else if (this.pos.config["stock_product"] === "outgoing_qty") {
                        if (event.outgoing_qty <= event.deny) {
                            await this.dialog.add(AlertDialog, {
                                title: _t("Deny Order"),
                                body: _t("%s is Out Of Stock", event.name),
                            });
                        } else {
                            super.addProductToOrder(event);
                        }
                    } else if (this.pos.config["stock_product"] === "incoming_qty") {
                        if (event.incoming_qty <= event.deny) {
                            await this.dialog.add(AlertDialog, {
                                title: _t("Deny Order"),
                                body: _t("%s is Out Of Stock", event.name),
                            });
                        } else {
                            super.addProductToOrder(event);
                        }
                    }
                } else {
                    super.addProductToOrder(event);
                }
            } else {
                super.addProductToOrder(event);
            }
        } else {
            super.addProductToOrder(event);
        }
    },
});
