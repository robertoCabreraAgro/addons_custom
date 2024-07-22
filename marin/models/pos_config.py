from odoo import _, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    active = fields.Boolean(default=True)

    def validate_stock_on_pos_order(self, order_lines_data):
        """Meant to be called from the POS UI. Checks if the stock is available for the order.
        Returns a list of the products with missing stock.
        """
        # Storage for the stock missing. Each slot is a `product.lot`.
        missing_items = []
        # Used to avoid negative stock when two or more order lines use the same lot.
        already_used_quantities = {}
        for line_data in order_lines_data:
            product = self.env["product.product"].browse(line_data["product_id"])
            quantity = line_data["quantity"]
            lot = self.env["stock.lot"]
            if line_data["lot"]:
                lot = lot.search(
                    [
                        ("product_id", "=", product.id),
                        ("name", "=", line_data["lot"]),
                    ],
                    limit=1,
                )
            available = self.env["stock.quant"]._get_available_quantity(
                product,
                self.picking_type_id.default_location_src_id,
                lot,
            )
            qty_key = "%s-%s" % (product.id, lot.id)
            if qty_key in already_used_quantities:
                available -= already_used_quantities[qty_key]
                available = max(available, 0)
                already_used_quantities[qty_key] += quantity
            else:
                already_used_quantities[qty_key] = quantity
            missing_qty = quantity - available if available < quantity else 0
            missing_items.append(missing_qty)
        return missing_items

    def open_pos_cash_transfer_wizard(self):
        session = self.session_ids[:1]
        payment = session.cash_transfer_payment_ids.filtered(lambda pay: pay.state == "draft")[:1]
        if payment:
            return {
                "name": _("Payments"),
                "type": "ir.actions.act_window",
                "res_model": "account.payment",
                "context": {"create": False},
                "view_mode": "form",
                "res_id": payment.id,
            }
        return session.open_pos_cash_transfer_wizard()
