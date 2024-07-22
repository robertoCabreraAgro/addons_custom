from odoo import api, fields, models
from odoo.tools import float_compare, float_is_zero


class PurchaseOrderInherit(models.Model):
    _inherit = "purchase.order"

    def _domain_partner_id(self):
        categories = []
        if self.env.user.has_group("marin.group_purchase_core_business"):
            categories.append(self.env.ref("marin.partner_category_supplier_core").id)
        if self.env.user.has_group("marin.partner_category_110"):
            categories.append(self.env.ref("marin.partner_category_110").id)
        if self.env.user.has_group("marin.group_purchase_general"):
            categories.append(self.env.ref("marin.partner_category_supplier_general").id)
        if not categories:
            return [("id", "=", False)]
        return [
            ("category_id", "in", categories),
            ("company_id", "in", (False, self.env.company.id)),
        ]

    # Override original fields
    partner_id = fields.Many2one(domain=_domain_partner_id)
    invoice_status = fields.Selection(
        selection_add=[("partially", "Partially billed"), ("over invoiced", "Over billed")]
    )
    receipt_status = fields.Selection(selection_add=[("no", "Nothing to receive"), ("over full", "Over received")])

    # New fields
    is_user_id_editable = fields.Boolean(
        compute="_compute_is_user_id_editable",
    )

    # Override original method
    @api.depends("state", "order_line.qty_to_invoice")
    def _get_invoiced(self):
        precision = self.env["decimal.precision"].precision_get("Product Unit of measure")
        for order in self:
            if order.state not in ("purchase", "done"):
                order.invoice_status = "no"
                continue

            qty1 = 0
            to_invoice = 0
            for line in order.order_line.filtered(lambda ln: not ln.display_type):
                qty1 += line.product_qty
                to_invoice += line.qty_to_invoice

            if not float_compare(qty1, to_invoice, precision_digits=precision):
                order.invoice_status = "to invoice"
            elif float_compare(qty1, to_invoice, precision_digits=precision) > 0 and not float_is_zero(
                to_invoice, precision_digits=precision
            ):
                order.invoice_status = "partially"
            elif float_is_zero(to_invoice, precision_digits=precision) and order.invoice_ids:
                order.invoice_status = "invoiced"
            elif float_compare(qty1, to_invoice, precision_digits=precision) < 1:
                order.invoice_status = "over invoiced"
            else:
                order.invoice_status = "no"

    # Override original method
    @api.depends("state", "order_line.qty_to_receive", "order_line.product_uom_qty")
    def _compute_receipt_status(self):
        precision = self.env["decimal.precision"].precision_get("Product Unit of measure")
        for order in self:
            if order.state not in ("purchase", "done"):
                order.receipt_status = "no"
                continue

            qty1 = 0
            to_receive = 0
            for line in order.order_line.filtered(lambda ln: not ln.display_type):
                qty1 += line.product_uom_qty
                to_receive += line.qty_to_receive

            if not float_compare(qty1, to_receive, precision_digits=precision):
                order.receipt_status = "pending"
            elif float_compare(qty1, to_receive, precision_digits=precision) > 0 and not float_is_zero(
                to_receive, precision_digits=precision
            ):
                order.receipt_status = "partial"
            elif float_is_zero(to_receive, precision_digits=precision):
                order.receipt_status = "full"
            elif float_compare(qty1, to_receive, precision_digits=precision) < 1:
                order.receipt_status = "over full"
            else:
                order.receipt_status = "no"

    def action_force_reception_status(self):
        self.write({"receipt_status": "full"})

    def action_unforce_reception_status(self):
        self._compute_receipt_status()

    def _compute_is_user_id_editable(self):
        self.is_user_id_editable = self.env.user.has_group(
            "purchase.group_purchase_manager"
        ) or not self.env.user.has_group("purchase_security.group_purchase_own_orders")
