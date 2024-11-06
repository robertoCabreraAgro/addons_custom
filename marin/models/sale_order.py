from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # Extended fields
    delivery_status = fields.Selection(
        selection_add=[("no", "Nothing to deliver"), ("over full", "Over delivered")]
    )
    margin = fields.Float(digits="Product Price")
    margin_percent = fields.Float(digits="Product Price")

    # New fields
    commercial_partner_id = fields.Many2one(
        related="partner_id.commercial_partner_id",
        store=True,
        index=True,
    )
    force_fully_invoiced = fields.Boolean()
    force_fully_delivered = fields.Boolean()
    route_id = fields.Many2one(
        "stock.route",
        "Route",
        domain=[("sale_selectable", "=", True)],
        help="When you change this field all the lines will be changed. "
             "After use it you will be able to change each line.",
    )
    season_id = fields.Many2one(
        "date.range",
        "AG season",
        help="Since every farmer can have several growing seasons the specific one "
             "can be selected.",
    )

    # Extend original method
    @api.depends("company_id", "user_id", "sale_order_template_id")
    def _compute_journal_id(self):
        res = super()._compute_journal_id()
        for order in self:
            if not order.journal_id:
                default_sale_journal_id = (
                    self.env["ir.default"]
                    .with_company(order.company_id.id)
                    ._get_model_defaults("sale.order")
                    .get("sale_journal_id")
                )
                if order.state in ("draft", "sent") or not order.ids:
                    order.journal_id = (
                        default_sale_journal_id
                        or order.user_id.with_company(
                            order.company_id.id
                        )._get_default_sale_journal_id()
                    )
        return res

    @api.depends("company_id", "partner_id", "amount_total", "commercial_partner_id.credit_limit")
    def _compute_partner_credit_warning(self):
        for order in self:
            order.with_company(order.company_id)
            order.partner_credit_warning = ""
            future_credit = order.commercial_partner_id.credit + (order.amount_total * order.currency_rate)
            show_warning = (
                order.company_id.account_use_credit_limit
                and order.state in ("draft", "sent")
                and future_credit > order.commercial_partner_id.credit_limit
            )
            if show_warning:
                order.partner_credit_warning = order.commercial_partner_id._build_credit_warning_message(
                    future_credit, order.company_id.currency_id
                )

    # Override original method
    @api.depends("state", "order_line.qty_to_deliver", "order_line.product_uom_qty")
    def _compute_delivery_status(self):
        precision = self.env["decimal.precision"].precision_get("Product Unit of measure")
        for order in self:
            if order.state not in ("sale", "done"):
                order.delivery_status = "no"
                continue

            qty1 = 0
            to_deliver = 0
            for line in order.order_line.filtered(lambda ln: not ln.display_type):
                qty1 += line.product_uom_qty
                to_deliver += line.qty_to_deliver

            if not float_compare(qty1, to_deliver, precision_digits=precision):
                order.delivery_status = "pending"
            elif float_compare(qty1, to_deliver, precision_digits=precision) > 0 and not float_is_zero(
                to_deliver, precision_digits=precision
            ):
                order.delivery_status = "partial"
            elif float_is_zero(to_deliver, precision_digits=precision):
                order.delivery_status = "full"
            elif float_compare(qty1, to_deliver, precision_digits=precision) < 1:
                order.delivery_status = "over full"
            else:
                order.delivery_status = "no"

    # Extend original method
    @api.depends("state", "order_line.invoice_status")
    def _compute_invoice_status(self):
        forced = self.filtered("force_fully_invoiced")
        forced.invoice_status = "invoiced"
        return super(SaleOrder, self - forced)._compute_invoice_status()

    @api.onchange("route_id")
    def _onchange_route_id(self):
        """We could do sale order line route_id field compute store writable.
        But this field is created by Odoo so I prefer not modify it.
        """
        self.order_line.route_id = self.route_id

    def action_sale_authorize_debt(self):
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

    def action_force_delivery_status(self):
        self.write({"delivery_status": "full"})

    def action_unforce_delivery_status(self):
        self._compute_delivery_status()

    def action_recompute_invoice_status(self):
        self.order_line._compute_invoice_status()
        self._compute_invoice_status()

    def action_force_invoice_status(self):
        self.force_fully_invoiced = True
        self._compute_invoice_status()

    def action_unforce_invoice_status(self):
        self.force_fully_invoiced = False
        self._compute_invoice_status()

    def action_open_order_lines(self):
        action = self.env["ir.actions.act_window"]._for_xml_id("marin.action_sale_order_line")
        action["domain"] = [("id", "in", self.order_line.ids)]
        return action

    def validate_credit_limit(self):
        if self.partner_credit_warning and not self.payment_term_id.is_immediate:
            if self.commercial_partner_id.credit_on_hold:
                raise UserError(_(
                    "The partner's credit line has been held. Contact the Credit Manager."
                ))

            if not self.env.user.has_group("marin.group_account_debt_manager"):
                raise UserError(_(
                    "The Partner %s does not have an authorized credit line. "
                    "Contact the Credit Manager.",
                    self.partner_invoice_id.name,
                ))

            return self.action_sale_authorize_debt()

        return True

    # Extend original method
    def action_confirm(self):
        res = self.validate_credit_limit()
        if res is not True:
            return res

        return super().action_confirm()

    def action_clean_3_0(self):
        orders = self.filtered(lambda order: order.state == "sale")
        precision = self.env["decimal.precision"].precision_get("Product Unit of measure")
        lines = orders.mapped("order_line").filtered(
            lambda line: float_is_zero(line.product_uom_qty, precision_digits=precision)
            and float_is_zero(line.qty_delivered, precision_digits=precision)
            and float_is_zero(line.qty_invoiced, precision_digits=precision)
            and not line.invoice_lines
        )
        for line in lines:
            moves = line.move_ids.filtered(lambda sm: sm.state not in ["done", "cancel"])
            moves._action_cancel()
            line.with_context(avoid_check_unlink=True).unlink()

    def write(self, vals):
        res = super().write(vals)
        if "route_id" in vals:
            lines = self.mapped("order_line").filtered(
                lambda line: line.route_id.id != vals["route_id"]
            )
            lines.write({"route_id": vals["route_id"]})
        return res
