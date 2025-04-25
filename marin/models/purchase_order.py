from collections import defaultdict
from markupsafe import Markup

from odoo import api, fields, models
from odoo.tools.misc import clean_context


class PurchaseOrder(models.Model):
    """Inherit PurchaseOrder"""

    _inherit = "purchase.order"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    # Override original fields
    partner_id = fields.Many2one(
        domain=lambda self: self._get_partner_id_domain(),
    )

    # New fields
    count_approval = fields.Integer(
        compute="_compute_count_approval",
    )
    is_user_id_editable = fields.Boolean(
        compute="_compute_is_user_id_editable",
    )

    # --------------------------------------------------
    # CRUD METHODS
    # --------------------------------------------------

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

    # --------------------------------------------------
    # COMPUTE METHODS
    # --------------------------------------------------

    def _compute_count_approval(self):
        for order in self:
            approvals = (
                self.env["approval.product.line"]
                .search([("purchase_order_line_id.order_id", "=", order.id)])
                .mapped("approval_request_id")
            )
            order.count_approval = len(approvals)

    def _compute_is_user_id_editable(self):
        self.is_user_id_editable = self.env.user.has_group(
            "purchase.group_purchase_manager"
        ) or not self.env.user.has_group("purchase_security.group_purchase_own_orders")

    # Extend original method
    @api.depends("company_id", "user_id")
    def _compute_journal_id(self):
        for order in self:
            if not order.journal_id:
                default_journal_id = (
                    self.env["ir.default"]
                    .with_company(order.company_id.id)
                    ._get_model_defaults("purchase.order")
                    .get("purchase_journal_id")
                )
                if order.state == "draft" or not order.ids:
                    order.journal_id = (
                        default_journal_id
                        or order.user_id.with_company(
                            order.company_id.id
                        )._get_default_purchase_journal_id()
                    )
            if not order.journal_id:
                return super()._compute_journal_id()

    # Override original method
    @api.depends("state", "order_line_ids.transfer_state", "picking_ids")
    def _compute_transfer_state(self):
        confirmed_orders = self.filtered(lambda o: o.state == "purchase")
        (self - confirmed_orders).transfer_state = "no"

        if not confirmed_orders:
            return

        lines_domain = [
            ("is_downpayment", "=", False),
            ("display_type", "=", False),
            ("order_id", "in", confirmed_orders.ids),
        ]
        line_transfer_state_all = {}
        for order, transfer_state in self.env["purchase.order.line"]._read_group(
            lines_domain,
            ["order_id", "transfer_state"],
        ):
            if not order.id in line_transfer_state_all:
                line_transfer_state_all[order.id] = set()
            line_transfer_state_all[order.id].add(transfer_state)
        for order in confirmed_orders:
            states = line_transfer_state_all[order._origin.id]
            if not order.picking_ids or all(state == "to do" for state in states):
                order.transfer_state = "to do"
            elif any(state == "over done" for state in states):
                order.transfer_state = "over done"
            elif all(state == "done" for state in states):
                order.transfer_state = "done"
            elif any(state == "partially" for state in states) or (
                not any(state == "partially" for state in states)
                and any(state in ("to do", "done") for state in states)
            ):
                order.transfer_state = "partially"
            else:
                order.transfer_state = "no"

    # Override original method
    @api.depends("state", "order_line_ids.invoice_state", "invoice_ids")
    def _compute_invoice_state(self):
        confirmed_orders = self.filtered(lambda o: o.state == "purchase")
        (self - confirmed_orders).invoice_state = "no"
        
        if not confirmed_orders:
            return

        lines_domain = [
            ("is_downpayment", "=", False),
            ("display_type", "=", False),
            ("order_id", "in", confirmed_orders.ids),
        ]
        line_invoice_state_all = {}
        for order, invoice_state in self.env["purchase.order.line"]._read_group(
            lines_domain,
            ["order_id", "invoice_state"],
        ):
            if not order.id in line_invoice_state_all:
                line_invoice_state_all[order.id] = set()
            line_invoice_state_all[order.id].add(invoice_state)
        for order in confirmed_orders:
            states = line_invoice_state_all[order._origin.id]
            if not order.invoice_ids or all(state == "to do" for state in states):
                order.invoice_state = "to do"
            elif any(state == "over done" for state in states):
                order.invoice_state = "over done"
            elif all(state == "done" for state in states):
                order.invoice_state = "done"
            elif any(state == "partially" for state in states) or (
                not any(state == "partially" for state in states)
                and any(state in ("to do", "done") for state in states)
            ):
                order.invoice_state = "partially"
            else:
                order.invoice_state = "no"

    # --------------------------------------------------
    # ACTION METHODS
    # --------------------------------------------------

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

    def action_force_transfer_state(self):
        self.write({"transfer_state": "done"})

    def action_unforce_transfer_state(self):
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
