from collections import defaultdict
from markupsafe import Markup

from odoo import api, fields, models
from odoo.tools import float_compare, float_is_zero
from odoo.tools.misc import clean_context


class PurchaseOrderInherit(models.Model):
    _inherit = "purchase.order"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    # Override original fields
    partner_id = fields.Many2one(domain=lambda self: self._get_partner_id_domain())
    receipt_status = fields.Selection(
        selection_add=[("no", "Nothing to receive"), ("over full", "Over received")]
    )

    # New fields
    is_user_id_editable = fields.Boolean(
        compute="_compute_is_user_id_editable",
    )
    count_approval = fields.Integer(
        compute="_compute_count_approval",
    )

    def write(self, vals):
        if "state" in vals:
            orders_changed_state = self.filtered(
                lambda purchase_order: purchase_order.state != vals["state"]
            )
            if orders_changed_state:
                related_approval_product_lines = (
                    self.sudo()
                    .env["approval.product.line"]
                    .search(
                        domain=[
                            (
                                "purchase_order_line_id.order_id",
                                "in",
                                orders_changed_state.ids,
                            )
                        ],
                    )
                )
                if related_approval_product_lines:
                    grouped_product_lines = defaultdict(
                        lambda: defaultdict(lambda: self.env["approval.product.line"])
                    )
                    for product_line in related_approval_product_lines:
                        grouped_product_lines[product_line.approval_request_id][
                            product_line.purchase_order_line_id.order_id
                        ] |= product_line
                    self._log_po_state_change_to_approval_request_chatter(
                        vals["state"], grouped_product_lines
                    )
        return super().write(vals)

    def _compute_count_approval(self):
        for order in self:
            approvals = (
                self.env["approval.product.line"]
                .search([("purchase_order_line_id.order_id", "=", order.id)])
                .mapped("approval_request_id")
            )
            order.count_approval = len(approvals)

    # Override original method
    @api.depends("state", "invoice_ids", "order_line_ids.invoice_state")
    def _compute_invoice_state(self):
        for order in self:
            if order.state != "purchase":
                order.invoice_state = "no"
                continue

            order_lines = order.order_line_ids.filtered(lambda l: not l.display_type)
            if not order.invoice_ids or all(
                line.invoice_state == "to do" for line in order_lines
            ):
                order.invoice_state = "to do"
            elif all(line.invoice_state == "done" for line in order_lines):
                order.invoice_state = "done"
            elif any(line.invoice_state == "over done" for line in order_lines):
                order.invoice_state = "over done"
            elif (
                any(line.invoice_state == "partially" for line in order_lines)
                or not any(line.invoice_state == "partially" for line in order_lines)
                and any(line.invoice_state in ("to do", "done") for line in order_lines)
            ):
                order.invoice_state = "partially"
            else:
                order.invoice_state = "no"

    # Override original method
    @api.depends(
        "state", "order_line_ids.qty_to_receive", "order_line_ids.product_uom_qty"
    )
    def _compute_transfer_state(self):
        precision = self.env["decimal.precision"].precision_get(
            "Product Unit of measure"
        )
        for order in self:
            if order.state not in ("purchase", "done"):
                order.receipt_status = "no"
                continue

            qty1 = 0
            to_receive = 0
            for line in order.order_line_ids.filtered(lambda ln: not ln.display_type):
                qty1 += line.product_uom_qty
                to_receive += line.qty_to_receive

            if not float_compare(qty1, to_receive, precision_digits=precision):
                order.receipt_status = "pending"
            elif float_compare(
                qty1, to_receive, precision_digits=precision
            ) > 0 and not float_is_zero(to_receive, precision_digits=precision):
                order.receipt_status = "partial"
            elif float_is_zero(to_receive, precision_digits=precision):
                order.receipt_status = "full"
            elif float_compare(qty1, to_receive, precision_digits=precision) < 1:
                order.receipt_status = "over full"
            else:
                order.receipt_status = "no"

    def _compute_is_user_id_editable(self):
        self.is_user_id_editable = self.env.user.has_group(
            "purchase.group_purchase_manager"
        ) or not self.env.user.has_group("purchase_security.group_purchase_own_orders")

    def action_view_approval(self):
        self.ensure_one()
        approvals_ids = (
            self.env["approval.product.line"]
            .search([("purchase_order_line_id.order_id", "=", self.id)])
            .mapped("approval_request_id")
            .ids
        )
        domain = [("id", "in", approvals_ids)]
        action = {
            "name": _("Approvals"),
            "type": "ir.actions.act_window",
            "res_model": "approval.request",
            "view_mode": "list,form",
            "view_type": "list",
            # avoid 'default_name' context key propagation
            "context": clean_context(self.env.context),
            "domain": domain,
        }
        return action

    def action_force_reception_status(self):
        self.write({"receipt_status": "full"})

    def action_unforce_reception_status(self):
        self._compute_transfer_state()

    def _log_po_state_change_to_approval_request_chatter(
        self, new_state, grouped_product_lines
    ):
        for (
            approval_request,
            product_lines_by_purchase_order,
        ) in grouped_product_lines.items():
            for (
                purchase_order,
                product_lines,
            ) in product_lines_by_purchase_order.items():
                state_change_msg = purchase_order._prepare_state_change_msg(
                    purchase_order.state, new_state, product_lines
                )
                approval_request._message_log(body=state_change_msg)

    def _get_partner_id_domain(self):
        categories = []
        if self.env.user.has_group("marin.group_purchase_core_business"):
            categories.append(self.env.ref("marin.partner_category_supplier_core").id)

        if self.env.user.has_group("marin.group_purchase_general"):
            categories.append(
                self.env.ref("marin.partner_category_supplier_general").id
            )

        if self.env.user.has_group("marin.group_purchase_xiuman"):
            categories.append(self.env.ref("marin.partner_category_supplier_xiuman").id)

        if self.env.user.has_group("marin.group_purchase_potatoes"):
            categories.append(
                self.env.ref("marin.partner_category_supplier_potatoes").id
            )

        if not categories:
            return [("id", "=", False)]

        return [
            ("category_id", "in", categories),
            ("company_id", "in", (False, self.env.company.id)),
        ]

    def _prepare_state_change_msg(
        self, old_state, new_state, approval_request_products
    ):
        state_label = dict(self._fields["state"]._description_selection(self.env))
        return Markup("%(state_change_header)s<br> %(products_summary)s") % {
            "state_change_header": _(
                "RFQ %(rfq_name)s state has been changed: %(old_state_label)s -> %(new_state_label)s",
                rfq_name=self.name,
                old_state_label=state_label[old_state],
                new_state_label=state_label[new_state],
            ),
            "products_summary": Markup("%(header)s<br> <ul>%(products)s</ul>")
            % {
                "header": _("Products: "),
                "products": Markup().join(
                    Markup("<li>%(product_quantity)s %(product_name)s</li>")
                    % {
                        "product_quantity": product.quantity,
                        "product_name": product.product_id.name,
                    }
                    for product in approval_request_products
                ),
            },
        }
