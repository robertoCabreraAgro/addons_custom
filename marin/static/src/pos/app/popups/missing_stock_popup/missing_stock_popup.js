/** @odoo-module */

import {AbstractAwaitablePopup} from "@point_of_sale/app/popup/abstract_awaitable_popup";
import {_t} from "@web/core/l10n/translation";
import {Orderline} from "@point_of_sale/app/generic_components/orderline/orderline";
import {usePos} from "@point_of_sale/app/store/pos_hook";

class MissingStockPopup extends AbstractAwaitablePopup {
    setup() {
        super.setup();
        const editable_lines = {};
        this.pos = usePos();
        this.props.order_lines.forEach((line) => {
            // Used for display porpuses in the template OrderlineDetails
            const cloned = owl.reactive(line.clone());
            cloned.order = this.props.order;
            if (line.pack_lot_lines.length) {
                // We need to create a new class instance for the pack_lot_lines
                // to avoid modifiying the original order line.;
                cloned.setPackLotLines({
                    modifiedPackLotLines: [],
                    newPackLotLines: [{lot_name: line.pack_lot_lines[0].lot_name}],
                });
                cloned.set_quantity(line.get_quantity());
            }
            editable_lines[line.cid] = cloned;
        });
        this.state = owl.useState({
            new_lines: [],
            selected_line: null,
            current_lots: [],
            selected_lot: null,
            current_qty: 0,
            editable_lines,
        });
        owl.onMounted(() => {
            const lines = Object.values(editable_lines);
            if (lines.length == 1) {
                this._onClickOrderline(lines[0]);
            }
        });
    }
    async _onClickOrderline(line) {
        this.state.selected_line = line;
        this.state.selected_lot = null;
        this.state.current_qty = 0;
        this.state.current_lots = await this.pos.getProductLots(line.product);
    }
    isLineSelected(line) {
        return this.state.selected_line == null ? false : this.state.selected_line.cid == line.cid;
    }
    get new_lines_array() {
        return this.state.new_lines;
    }
    get lines_with_origin() {
        return Object.values(this.state.editable_lines);
    }
    setCurrentQty({currentTarget: {value}}) {
        this.state.current_qty = ~~value;
    }
    isSameLot(lot) {
        const selected = this.state.selected_line;
        if (!selected || !selected.pack_lot_lines.length) {
            return false;
        }
        return lot.name == selected.pack_lot_lines[0].lot_name;
    }
    selectLot(ev) {
        this.state.selected_lot = this.state.current_lots.find((lot) => lot.id == ev.currentTarget.value);
    }
    canAddLine() {
        if (
            !this.state.current_qty ||
            !this.state.selected_lot ||
            !this.state.selected_line ||
            this.isSameLot(this.state.selected_lot)
        ) {
            console.warn("this.state.current_qty", this.state.current_qty);
            console.warn("this.state.selected_lot", this.state.selected_lot);
            console.warn("this.state.selected_line", this.state.selected_line);
            return;
        }
        return true;
    }
    get addNewLineClass() {
        return {
            highlight: this.canAddLine(),
        };
    }
    async switchLot(lot) {
        if (!this.state.selected_line) {
            return;
        }
        const oldQty = this.state.selected_line.get_quantity();
        this.state.selected_line.setPackLotLines({
            modifiedPackLotLines: [],
            newPackLotLines: [
                {
                    lot_name: lot.name,
                },
            ],
        });
        this.state.selected_line.set_quantity(oldQty);
        await this.updateStockMissingQty();
    }
    async updateStockMissingQty() {
        const lines = this.lines_with_origin.concat(this.new_lines_array);
        const missing_inventory = await this.props.order.getMissingInventory(lines);
        lines.forEach((line, idx) => {
            line.stock_lot_qty_missing = missing_inventory[idx];
        });
    }
    async addNewLine() {
        if (!this.canAddLine()) {
            return;
        }
        const diminished_qty = Math.max(this.state.selected_line.get_quantity() - this.state.current_qty, 0);
        this.state.selected_line.set_quantity(diminished_qty);
        const newLine = this.state.selected_line.clone();
        newLine.order = this.state.selected_line.order;
        newLine.setPackLotLines({
            modifiedPackLotLines: [],
            newPackLotLines: [
                {
                    lot_name: this.state.selected_lot.name,
                },
            ],
        });
        newLine.set_quantity(this.state.current_qty);
        this.state.new_lines.push(newLine);
        this.state.current_qty = 0;
        this.state.selected_lot = null;
        await this.updateStockMissingQty();
    }
    confirm() {
        const linesByCID = this.props.order_lines.reduce((obj, line) => {
            obj[line.cid] = line;
            return obj;
        }, {});
        for (const cid in this.state.editable_lines) {
            this.props.order.removeOrderline(linesByCID[cid]);
            const newLine = this.state.editable_lines[cid];
            if (newLine.get_quantity() > 0) {
                this.props.order.add_orderline(newLine);
            }
        }
        for (const line of this.state.new_lines) {
            this.props.order.add_orderline(line);
        }
        return super.confirm();
    }
}

MissingStockPopup.template = "marin.MissingStockPopup";
MissingStockPopup.components = {
    Orderline,
};

export {MissingStockPopup};
