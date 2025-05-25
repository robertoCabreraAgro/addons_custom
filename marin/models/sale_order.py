from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero
from odoo.tools.translate import _


class SaleOrder(models.Model):
    """Inherit SaleOrder"""

    _inherit = "sale.order"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    # New fields
    commercial_partner_id = fields.Many2one(
        related="partner_id.commercial_partner_id",
        store=True,
        index=True,
    )
    route_id = fields.Many2one(
        comodel_name="stock.route",
        string="Route",
        domain=[("sale_selectable", "=", True)],
        help="When you change this field all the lines will be changed. "
        "After use it you will be able to change each line.",
    )
    season_id = fields.Many2one(
        comodel_name="date.range",
        string="AG season",
        help="Since every farmer can have several growing seasons the specific one "
        "can be selected.",
    )
    force_fully_invoiced = fields.Boolean()
    force_fully_delivered = fields.Boolean()

    # --------------------------------------------------
    # CRUD METHODS
    # --------------------------------------------------

    def write(self, vals):
        res = super().write(vals)
        if "route_id" in vals:
            lines = self.mapped("line_ids").filtered(
                lambda line: line.route_id.id != vals["route_id"]
            )
            lines.write({"route_id": vals["route_id"]})
        return res

    # --------------------------------------------------
    # COMPUTE METHODS
    # --------------------------------------------------

    # Extend original method
    @api.depends("company_id", "user_id", "sale_order_template_id")
    def _compute_journal_id(self):
        for order in self:
            if not order.journal_id:
                default_journal_id = (
                    self.env["ir.default"]
                    .with_company(order.company_id.id)
                    ._get_model_defaults("sale.order")
                    .get("sale_journal_id")
                )
                if order.state == "draft" or not order.ids:
                    order.journal_id = (
                        default_journal_id
                        or order.user_id.with_company(
                            order.company_id.id
                        )._get_default_sale_journal_id()
                    )
            if not order.journal_id:
                return super()._compute_journal_id()

    @api.depends(
        "company_id", "partner_id", "amount_total", "commercial_partner_id.credit_limit"
    )
    def _compute_partner_credit_warning(self):
        for order in self:
            order.with_company(order.company_id)
            order.partner_credit_warning = ""
            future_credit = order.commercial_partner_id.credit + (
                order.amount_total * order.currency_rate
            )
            show_warning = (
                order.company_id.account_use_credit_limit
                and order.state in ("draft", "sent")
                and future_credit > order.commercial_partner_id.credit_limit
            )
            if show_warning:
                order.partner_credit_warning = (
                    order.commercial_partner_id._build_credit_warning_message(
                        future_credit, order.company_id.currency_id
                    )
                )

    # Override original method
    @api.depends("state", "line_ids.transfer_state", "picking_ids")
    def _compute_transfer_state(self):
        confirmed_orders = self.filtered(lambda o: o.state == "sale")
        (self - confirmed_orders).transfer_state = "no"

        if not confirmed_orders:
            return

        lines_domain = [
            ("is_downpayment", "=", False),
            ("display_type", "=", False),
            ("order_id", "in", confirmed_orders.ids),
        ]
        line_transfer_state_all = {}
        for order, transfer_state in self.env["sale.order.line"]._read_group(
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
    @api.depends("state", "line_ids.invoice_state", "invoice_ids")
    def _compute_invoice_state(self):
        # force logic
        forced_orders = self.filtered("force_fully_invoiced")
        forced_orders.invoice_state = "done"

        unforced_orders = self - forced_orders
        if not unforced_orders:
            return

        return super(SaleOrder, unforced_orders)._compute_invoice_state()

    # --------------------------------------------------
    # ONCHANGE METHODS
    # --------------------------------------------------

    @api.onchange("route_id")
    def _onchange_route_id(self):
        """We could do sale order line route_id field compute store writable.
        But this field is created by Odoo so I prefer not modify it.
        """
        self.line_ids.route_id = self.route_id

    # --------------------------------------------------
    # ACTION METHODS
    # --------------------------------------------------

    def action_authorize_debt_wizard(self):
        view = self.env.ref("marin.view_authorize_debt_wizard_form")
        return {
            "name": _("Authorize debt"),
            "type": "ir.actions.act_window",
            "res_model": "authorize.debt.wizard",
            "view_mode": "form",
            "views": [(view.id, "form")],
            "view_id": view.id,
            "target": "new",
            "context": {"active_model": "sale.order", "active_ids": self.ids},
        }

    def action_force_transfer_state(self):
        self.write({"transfer_state": "done"})

    def action_unforce_transfer_state(self):
        self._compute_transfer_state()

    def action_recompute_invoice_state(self):
        self.line_ids._compute_invoice_state()
        self._compute_invoice_state()

    def action_force_invoice_state(self):
        self.force_fully_invoiced = True
        self._compute_invoice_state()

    def action_unforce_invoice_state(self):
        self.force_fully_invoiced = False
        self._compute_invoice_state()

    def action_view_order_lines(self):
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "marin.action_sale_order_line"
        )
        action["domain"] = [("id", "in", self.line_ids.ids)]
        return action

    def _authorize_credit_limit(self):
        """Authorize credit limit based on partner status and user permissions.

        Returns:
            bool|dict: True if authorized automatically,
                       debt authorization action if requires approval
        """
        # User permissions
        user_authorized = self.env.user.has_group(
            "partner_credit_checks.allow_to_validate_credit_checks"
        ) and self.env.user.has_group("marin.group_account_debt_manager")
        if not user_authorized:
            return True

        # Partner conditions
        partner_eligible = (
            self.partner_id.credit_status != "legal" and self.partner_credit_warning
        )

        # Financial conditions
        payment_eligible = not self.payment_term_id.is_immediate

        if partner_eligible and payment_eligible:
            return self.action_authorize_debt_wizard()

        return True

    # Extend original method
    def action_confirm(self):
        res = self._authorize_credit_limit()
        if res is not True:
            return res
        return super().action_confirm()

    def action_clean_3_0(self):
        orders = self.filtered(lambda order: order.state == "sale")
        precision = self.env["decimal.precision"].precision_get(
            "Product Unit of measure"
        )
        lines = orders.mapped("line_ids").filtered(
            lambda line: float_is_zero(line.product_uom_qty, precision_digits=precision)
            and float_is_zero(line.qty_transfered, precision_digits=precision)
            and float_is_zero(line.qty_invoiced, precision_digits=precision)
            and not line.invoice_lines
        )
        for line in lines:
            moves = line.move_ids.filtered(
                lambda sm: sm.state not in ["done", "cancel"]
            )
            moves._action_cancel()
            line.with_context(avoid_check_unlink=True).unlink()
