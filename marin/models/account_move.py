from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tools.float_utils import float_compare
from odoo.tools.misc import formatLang
from odoo.tools.translate import _


class AccountMove(models.Model):
    _inherit = "account.move"

    # Extended fields
    invoice_date = fields.Date(
        compute="_compute_invoice_date",
        store=True,
        precompute=True,
        readonly=False,
        copy=True,
    )
    invoice_origin = fields.Char(readonly=False)
    l10n_mx_edi_payment_policy = fields.Selection(store=True, readonly=False)
    l10n_mx_edi_usage = fields.Selection(selection_add=[("CP01", "Payments")])

    # New fields
    journal_type = fields.Selection(
        related="journal_id.type", string="Journal type", store=True, readonly=True
    )
    force_payment_policy_pue = fields.Boolean(
        string="Force PUE",
        default=False,
    )
    x_stored = fields.Boolean(
        string="Stored",
        tracking=True,
        help="If this checkbox is ticked, it means that a management representative has "
        "received and stored a printed invoice on credit signed by the customer. ",
    )
    show_update_line_account = fields.Boolean(string="Has Journal Changed", store=False)
    pos_session_origin_id = fields.Many2one(
        comodel_name="pos.session",
        string="POS session",
    )
    count_approval = fields.Integer(
        compute="_compute_count_approval",
    )

    # Extend original method
    def unlink(self):
        cancelled_moves = self.env["account.move"]
        if self.env.user.has_group("marin.group_account_move_force_removal"):
            cancelled_moves |= self.filtered(lambda m: m.state == "cancel")
            super(AccountMove, cancelled_moves.with_context(force_delete=True)).unlink()
        return super(AccountMove, self - cancelled_moves).unlink()

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------

    # Override original method
    @api.depends("line_ids.purchase_line_ids", "line_ids.product_id")
    def _compute_hide_purchase_matching(self):
        """OVERRIDE to add condition that check if product_id is defined.
        More context: Task #5643
        https://agromarin.mx/odoo/all-tasks/5643
        """
        for move in self:
            if any(
                il.display_type == "product"
                and not bool(il.purchase_line_ids)
                and bool(il.product_id)
                for il in move.invoice_line_ids
            ):
                move.hide_purchase_matching = False
                continue

            move.hide_purchase_matching = True

    # Override original method
    @api.depends("company_id", "currency_id", "partner_id", "amount_total")
    def _compute_partner_credit_warning(self):
        for invoice in self:
            invoice.with_company(invoice.company_id)
            invoice.partner_credit_warning = ""
            amount_total_currency = (
                invoice.currency_id._convert(
                    invoice.amount_total,
                    invoice.company_currency_id,
                    invoice.company_id,
                    invoice.date,
                )
                if invoice.move_type == "out_invoice"
                else 0
            )
            show_warning = (
                invoice.company_id.account_use_credit_limit
                and invoice.state == "draft"
                and invoice.commercial_partner_id
                and invoice.commercial_partner_id.credit_limit_available
                < amount_total_currency
            )
            if show_warning:
                future_credit = (
                    invoice.commercial_partner_id.credit + amount_total_currency
                )
                invoice.partner_credit_warning = (
                    invoice.commercial_partner_id._build_credit_warning_message(
                        future_credit, invoice.company_id.currency_id
                    )
                )

    @api.depends("move_type")
    def _compute_invoice_date(self):
        for move in self:
            invoice_date = fields.Date.today()
            if move.move_type == "entry":
                invoice_date = False
            move.invoice_date = invoice_date

    # Exxtend original method
    @api.depends("needed_terms")
    def _compute_invoice_date_due(self):
        for move in self:
            if move.invoice_payment_term_id and move.invoice_date and not move.line_ids:
                invoice_payment_terms = move.invoice_payment_term_id._compute_terms(
                    date_ref=move.invoice_date,
                    currency=move.currency_id,
                    company=move.company_id,
                    tax_amount=0.0,
                    tax_amount_currency=0.0,
                    sign=1,
                    untaxed_amount=1.0,
                    untaxed_amount_currency=1.0,
                    cash_rounding=move.invoice_cash_rounding_id,
                )
                move.invoice_date_due = max(
                    [d["date"] for d in invoice_payment_terms["line_ids"]]
                )
            else:
                super()._compute_invoice_date_due()

    # Override original method
    @api.depends(
        "move_type", "company_currency_id", "origin_payment_id", "statement_line_id"
    )
    def _compute_l10n_mx_edi_is_cfdi_needed(self):
        for move in self:
            move.l10n_mx_edi_is_cfdi_needed = (
                move.country_code == "MX"
                and move.company_currency_id.name == "MXN"
                and move.journal_id.x_treatment in ("fiscal_simulated", "fiscal_real")
                and (move.is_sale_document() or move._l10n_mx_edi_is_cfdi_payment())
            )

    # Override original method
    @api.depends(
        "partner_id",
        "l10n_mx_edi_is_cfdi_needed",
        "l10n_mx_edi_cfdi_origin",
    )
    def _compute_l10n_mx_edi_cfdi_to_public(self):
        for move in self:
            if move.move_type == "out_refund" and "global_sent" in set(
                move._l10n_mx_edi_get_refund_original_invoices().mapped(
                    "l10n_mx_edi_cfdi_state"
                )
            ):
                move.l10n_mx_edi_cfdi_to_public = True
            elif (
                move.partner_id
                and move.l10n_mx_edi_is_cfdi_needed
                and not move.l10n_mx_edi_cfdi_to_public
            ):
                cfdi_values = self.env["l10n_mx_edi.document"]._get_company_cfdi_values(
                    move.company_id
                )
                self.env["l10n_mx_edi.document"]._add_customer_cfdi_values(
                    cfdi_values,
                    customer=move.partner_id,
                )
                move.l10n_mx_edi_cfdi_to_public = (
                    cfdi_values["receptor"]["rfc"] == "XAXX010101000"
                )
            else:
                move.l10n_mx_edi_cfdi_to_public = False

    # Override original method
    @api.depends(
        "move_type",
        "invoice_date",
        "invoice_date_due",
        "invoice_payment_term_id",
        "force_payment_policy_pue",
    )
    def _compute_l10n_mx_edi_payment_policy(self):
        for move in self:
            move.l10n_mx_edi_payment_policy = False
            if (
                move.is_sale_document(include_receipts=True)
                and move.l10n_mx_edi_is_cfdi_needed
            ):
                move.l10n_mx_edi_payment_policy = "PUE"
                if (
                    move.move_type == "out_invoice"
                    and not move.l10n_mx_edi_cfdi_to_public
                    and move.invoice_date
                    and move.invoice_date_due
                    and (
                        move.invoice_date_due.month > move.invoice_date.month
                        or move.invoice_date_due.year > move.invoice_date.year
                        # This is not always true
                        # or len(move.invoice_payment_term_id.line_ids) > 1
                    )
                ):
                    move.l10n_mx_edi_payment_policy = "PPD"
                    if move.force_payment_policy_pue:
                        move.l10n_mx_edi_payment_policy = "PUE"

    def _compute_count_approval(self):
        for move in self:
            approvals = (
                self.env["approval.product.line"]
                .search([("account_move_id", "=", move.id)])
                .mapped("approval_request_id")
            )
            move.count_approval = len(approvals)

    @api.onchange("journal_id")
    def _onchange_journal_id_show_update_lines(self):
        self.show_update_line_account = bool(self.line_ids)

    def _pre_post_invoice_edi_amounts_match_validation(self):
        for invoice in self.filtered(lambda i: i.is_invoice()):
            if (invoice.x_check_tax or invoice.x_check_total) and (
                float_compare(
                    invoice.x_check_total,
                    invoice.amount_total,
                    precision_rounding=invoice.currency_id.rounding,
                )
                or float_compare(
                    invoice.x_check_tax,
                    invoice.amount_tax,
                    precision_rounding=invoice.currency_id.rounding,
                )
            ):
                raise UserError(
                    _(
                        "EDI amounts doesn't match with entry ones.\n\n"
                        "Total amount: %s --> Verification total amount: %s. Difference: %s\n"
                        "Tax amount: %s --> Verification tax amount: %s. Difference: %s\n",
                        formatLang(self.env, invoice.amount_total),
                        formatLang(self.env, invoice.x_check_total),
                        formatLang(self.env, invoice.x_total_difference),
                        formatLang(self.env, invoice.amount_tax),
                        formatLang(self.env, invoice.x_check_tax),
                        formatLang(self.env, invoice.x_tax_difference),
                    )
                )

    def _pre_post_invoice_credit_limit_validation(self):
        for invoice in self.filtered(
            lambda i: i.move_type == "out_invoice"
            and i.partner_credit_warning
            and not i.invoice_payment_term_id.is_immediate
        ):
            if invoice.commercial_partner_id.credit_on_hold:
                raise UserError(
                    _(
                        "The Partner's %s credit line has been held. Contact the Credit Manager.",
                        invoice.commercial_partner_id.name,
                    )
                )

            if not self.env.user.has_group("marin.group_account_debt_manager"):
                raise UserError(
                    _(
                        "The Partner %s does not have enough credit line. Contact the Credit Manager.",
                        invoice.commercial_partner_id.name,
                    )
                )

            authorized = self._context.get("debt_authorized")
            if authorized or self.env["ir.config_parameter"].sudo().get_param(
                "marin.avoid_authorize_debt"
            ):
                return True

            return invoice.action_authorize_debt_wizard()

        return True

    def action_post(self):
        self._pre_post_invoice_edi_amounts_match_validation()
        res = self._pre_post_invoice_credit_limit_validation()
        if res is not True:
            return res

        return super().action_post()

    def button_set_stored(self):
        for move in self:
            move.x_stored = True

    def action_update_line_account(self):
        self.ensure_one()
        self.line_ids._compute_account_id()
        self.show_update_line_account = False

    def action_view_move_lines(self):
        return {
            "name": _("Move Lines"),
            "type": "ir.actions.act_window",
            "res_model": "account.move.line",
            "view_mode": "list",
            "views": [
                (self.env.ref("account.view_move_line_tree").id, "list"),
                (False, "form"),
            ],
            "context": {"search_default_group_by_move": True},
            "domain": [("id", "in", self.line_ids.ids)],
        }

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
            "context": {"active_model": "account.move", "active_ids": self.ids},
        }

    def action_cash_discount_wizard(self):
        return {
            "name": _("Register cash discount"),
            "type": "ir.actions.act_window",
            "res_model": "account.invoice.cash.discount",
            "view_mode": "form",
            "target": "new",
            "context": {"active_model": "account.move", "active_ids": self.ids},
        }

    def action_view_approval(self):
        self.ensure_one()
        approvals_ids = (
            self.env["approval.product.line"]
            .search([("account_move_id", "=", self.id)])
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
            "context": clean_context(
                self.env.context
            ),  # avoid 'default_name' context key propagation
            "domain": domain,
        }
        return action

    def _prepare_purchase_order_vals(self):
        self.ensure_one()
        return {
            "company_id": self.company_id.id,
            "currency_id": self.currency_id.id,
            "partner_id": self.commercial_partner_id.id,
            "dest_address_id": False,  # False since only supported in stock
            "date_order": self.invoice_date,
            "fiscal_position_id": (
                self.fiscal_position_id
                or self.fiscal_position_id._get_fiscal_position(
                    self.commercial_partner_id
                )
            ).id,
            "payment_term_id": self.invoice_payment_term_id.id,
            "origin": self.name,
            "invoice_status": "invoiced",
        }

    def _prepare_purchase_line_vals(self, move, purchase):
        self.ensure_one()
        purchase_line_vals = {}
        fpos = purchase.fiscal_position_id
        for line in move.invoice_line_ids.filtered(
            lambda ln: ln.display_type == "product"
        ):
            taxes = fpos.map_tax(line.product_id.supplier_tax_ids)
            if taxes:
                taxes = taxes.filtered(lambda t: t.company_id.id == self.company_id.id)
            purchase_line_vals[line.id] = {
                "order_id": purchase.id,
                "product_id": line.product_id.id,
                "name": (
                    "[%s] %s" % (line.product_id.default_code, line.name)
                    if line.product_id.default_code
                    else line.name
                ),
                "product_qty": line.quantity,
                "product_uom": line.product_uom_id.id,
                "price_unit": line.price_unit,
                "date_planned": fields.Date.from_string(purchase.date_order),
                "tax_ids": [Command.set(taxes.ids)],
                "analytic_distribution": line.analytic_distribution,
            }
        return purchase_line_vals

    def create_purchase_order(self):
        for move in self:
            if any(not line.product_id for line in move.invoice_line_ids):
                raise UserError(
                    _("Some move lines does not have a product set. Please review")
                )

            purchase_exist = self.env["purchase.order"].search(
                [
                    ("partner_id", "=", self.commercial_partner_id.id),
                    ("company_id", "=", self.company_id.id),
                    ("origin", "=", self.name),
                ]
            )
            if purchase_exist and len(purchase_exist) >= 1:
                raise UserError(
                    _(
                        "More than one Purchase Orders with the same origin have been found. "
                        "Please review"
                    )
                )

            if not purchase_exist:
                purchase_exist = self.env["purchase.order"].create(
                    self._prepare_purchase_order_vals()
                )
                purchase_line_vals = self._prepare_purchase_line_vals(
                    move, purchase_exist
                )
                for line, vals in purchase_line_vals.items():
                    move_line = self.env["account.move.line"].browse(int(line))
                    po_line = self.env["purchase.order.line"].create(vals)
                    move_line.purchase_line_ids= po_line.id
        return True
