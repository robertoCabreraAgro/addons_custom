from datetime import timedelta
from itertools import combinations

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tools.float_utils import float_compare
from odoo.tools.misc import clean_context, formatLang


class AccountMove(models.Model):
    """Inherit AccountMove"""

    _inherit = "account.move"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

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
        related="journal_id.type",
        string="Journal type",
        store=True,
        readonly=True,
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
    x_ignore_purchase_bill_matching = fields.Boolean(
        string="Ignore Purchase Bill Matching",
        tracking=True,
        help="If this checkbox is ticked, it means when launching the reconciliation "
        "of the vendor bill with purchase lines, the lines belonging to this entry will be ignored.",
    )
    show_update_line_account = fields.Boolean(
        string="Has Journal Changed",
        store=False,
    )
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

    # Extend original method
    @api.depends("needed_terms")
    def _compute_invoice_date_due(self):
        """Compute invoice due date based on payment terms and invoice date.

        This method optimizes the computation by filtering moves that have payment terms
        and invoice dates but no line items yet. For these moves, it calculates the
        due date using the payment term configuration. All other moves are handled
        by the parent method.

        The due date is determined by computing payment terms and selecting the
        maximum date from all payment term lines.
        """
        moves_to_compute = self.filtered(
            lambda move: move.invoice_payment_term_id
            and move.invoice_date
            and not move.line_ids
        )
        for move in moves_to_compute:
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
                d["date"] for d in invoice_payment_terms["line_ids"]
            )

        return super(AccountMove, self - moves_to_compute)._compute_invoice_date_due()

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
                    self.env._(
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

    def _authorize_credit_limit(self):
        """Validate invoice against credit limits with consistent authorization logic.

        Returns:
            bool|dict: True if authorized, debt wizard action if requires approval
        Raises:
            UserError: If credit is on hold or user lacks permissions
        """

        # User permissions
        user_authorized = self._context.get("debt_authorized") or (
            self.env.user.has_group(
                "partner_credit_checks.allow_to_validate_credit_checks"
            )
            and self.env.user.has_group("marin.group_account_debt_manager")
        )
        if not user_authorized:
            return True

        # Financial conditions
        invoices_elegible = self.filtered(
            lambda i: (
                i.move_type == "out_invoice"
                and not i.invoice_payment_term_id.is_immediate
            )
        )
        for invoice in invoices_elegible:
            # Partner conditions
            partner_eligible = (
                invoice.partner_id.credit_status != "legal"
                and invoice.partner_credit_warning
            )

            if partner_eligible:
                return self.action_authorize_debt_wizard()

        return True

    def action_post(self):
        amounts_match_validation = self._context.get("amounts_match_validation", True)
        if amounts_match_validation:
            self._pre_post_invoice_edi_amounts_match_validation()

        res = self._authorize_credit_limit()
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
            "name": self.env._("Move Lines"),
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
            "name": self.env._("Authorize debt"),
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
            "name": self.env._("Register cash discount"),
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
            "name": self.env._("Approvals"),
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
            "invoice_state": "done",
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
                    self.env._(
                        "Some move lines does not have a product set. Please review"
                    )
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
                    self.env._(
                        "More than one Purchase Orders with the same origin have been found. Please review"
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
                    move_line.purchase_line_ids = po_line.id
        return True

    @api.depends("state", "l10n_mx_edi_cfdi_state", "l10n_mx_edi_cfdi_sat_state")
    def _compute_l10n_mx_edi_update_sat_needed(self):
        purchase_moves = self.filtered(
            lambda m: m.is_purchase_document() and m.l10n_mx_edi_invoice_document_ids
        )
        for move in purchase_moves:
            move.l10n_mx_edi_update_sat_needed = True
        return super(
            AccountMove, self - purchase_moves
        )._compute_l10n_mx_edi_update_sat_needed()

    def _get_sat_status_cancellation_message(self):
        """Generate the message body for cancellation notification."""
        self.ensure_one()
        # Create clickable link to the document
        document_link = f'<a href="#" data-oe-model="{self._name}" data-oe-id="{self.id}">{self.name or "N/A"}</a>'

        # Simple message with just alert and clickable document link
        html_content = (
            f"<p>🚨 <strong>Cancelación detectada en SAT</strong></p>"
            f"<ul><li><strong>Factura:</strong> {document_link}</li></ul>"
            f"<p><em>Por favor, revisar y tomar las acciones correspondientes.</em></p>"
        )
        return Markup(html_content)

    # -------------------------------------------------------------------------
    # RECONCILIATION METHODS (Task 10105)
    # -------------------------------------------------------------------------

    def _get_invoice_reconcilable_lines(self, move):
        """Get invoice lines that can be reconciled.

        Args:
            move (account.move): The invoice to get reconcilable lines from

        Returns:
            account.move.line: Lines with residual amount that can be reconciled
        """
        account_type = (
            "asset_receivable"
            if move.move_type in ["out_invoice", "out_refund"]
            else "liability_payable"
        )
        return move.line_ids.filtered(
            lambda inv_line: inv_line.account_id.account_type == account_type
            and inv_line.amount_residual
        )

    def _build_payment_search_domain(self, move, invoice_line, date_range=None):
        """Build search domain for payment lines.

        Args:
            move (account.move): The invoice being reconciled
            invoice_line (account.move.line): The invoice line to reconcile
            date_range (dict, optional): Dict with 'date_from' and 'date_to' keys

        Returns:
            list: Domain for searching payment lines
        """
        domain = [
            ("account_id", "=", invoice_line.account_id.id),
            (
                "partner_id",
                "in",
                [move.partner_id.id, move.partner_id.commercial_partner_id.id]
            ),
            ("reconciled", "=", False),
            ("parent_state", "=", "posted"),
            ("id", "!=", invoice_line.id),  # Not the same line
        ]

        # Add date range filter if provided
        if date_range:
            domain.extend(
                [
                    ("date", ">=", date_range["date_from"]),
                    ("date", "<=", date_range["date_to"]),
                ]
            )

        # Filter payment lines that have opposite sign
        if invoice_line.amount_residual > 0:  # Debit (receivable)
            domain.append(("amount_residual", "<", 0))  # Credit payments
        else:  # Credit (payable)
            domain.append(("amount_residual", ">", 0))  # Debit payments

        return domain

    def _prepare_reconciliation_result(
        self, reconciled_count, partially_reconciled_count, errors, title_suffix
    ):
        """Prepare standardized result notification for reconciliation methods.

        Args:
            reconciled_count (int): Number of fully reconciled invoices
            partially_reconciled_count (int): Number of partially reconciled invoices
            errors (list): List of error messages
            title_suffix (str): Suffix to add to the notification title

        Returns:
            dict: Action dictionary for displaying notification
        """
        message_parts = []
        if reconciled_count > 0:
            message_parts.append(
                self.env._("%s invoice(s) reconciled successfully.", reconciled_count)
            )
        if partially_reconciled_count > 0:
            message_parts.append(
                self.env._(
                    "%s invoice(s) partially reconciled.", partially_reconciled_count
                )
            )

        if not message_parts:
            if (
                not partially_reconciled_count
            ):  # Only for methods that don't track partial reconciliation
                message = self.env._(
                    "No invoices could be reconciled with %s criteria.",
                    title_suffix.lower(),
                )
            else:
                message = self.env._("No invoices could be reconciled.")
        else:
            message = " ".join(message_parts)

        if errors:
            message += "\n\n" + self.env._("Errors:") + "\n" + "\n".join(errors)

        success_count = reconciled_count + partially_reconciled_count
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Auto Reconciliation - %s", title_suffix),
                "message": message,
                "type": "success" if success_count > 0 else "warning",
                "sticky": True,
            },
        }

    def action_auto_reconcile_ideal(self):
        """Auto-reconcile using ideal criteria: same partner, exact amount, same date."""
        reconciled_count = 0
        errors = []

        for move in self:
            try:
                # Validations
                if move.state != "posted":
                    errors.append(self.env._("Invoice %s is not posted", move.name))
                    continue

                if move.payment_state == "paid":
                    errors.append(self.env._("Invoice %s is already paid", move.name))
                    continue

                # Get receivable/payable lines with residual amount
                invoice_lines = self._get_invoice_reconcilable_lines(move)

                if not invoice_lines:
                    errors.append(
                        self.env._("Invoice %s has no lines to reconcile", move.name)
                    )
                    continue

                # Search for payment lines with ideal criteria
                for invoice_line in invoice_lines:
                    domain = self._build_payment_search_domain(
                        move,
                        invoice_line,
                        date_range={
                            "date_from": move.invoice_date,
                            "date_to": move.invoice_date,
                        },
                    )
                    # Add exact amount match for ideal criteria
                    domain.append(
                        ("amount_residual", "=", -invoice_line.amount_residual)
                    )
                    payment_line = self.env["account.move.line"].search(
                        domain, order="date asc, id asc", limit=1
                    )

                    if payment_line:
                        # Perform reconciliation
                        (invoice_line + payment_line).reconcile()
                        # Add post-message to invoice
                        move.message_post(
                            body=Markup(
                                self.env._(
                                    "Automatic reconciliation applied: <strong>Ideal</strong>"
                                    "- Same partner, exact amount, same date"
                                )
                            ),
                            message_type="notification",
                        )
                        reconciled_count += 1

            except Exception as e:
                errors.append(self.env._("Error reconciling %s: %s", move.name, str(e)))

        # Prepare result message
        return self._prepare_reconciliation_result(reconciled_count, 0, errors, "Ideal")

    def action_auto_reconcile_semi_ideal(self):
        """Auto-reconcile using semi-ideal criteria: same partner, exact amount, date within range."""

        reconciled_count = 0
        errors = []

        for move in self:
            try:
                # Validations
                if move.state != "posted":
                    errors.append(self.env._("Invoice %s is not posted", move.name))
                    continue

                if move.payment_state == "paid":
                    errors.append(self.env._("Invoice %s is already paid", move.name))
                    continue

                # Get receivable/payable lines with residual amount
                invoice_lines = self._get_invoice_reconcilable_lines(move)

                if not invoice_lines:
                    errors.append(
                        self.env._("Invoice %s has no lines to reconcile", move.name)
                    )
                    continue

                # Calculate date range (1 month before to 2 months after)
                invoice_date = move.invoice_date
                date_from = invoice_date - timedelta(days=30)  # 1 month before
                date_to = invoice_date + timedelta(days=60)  # 2 months after

                # Search for payment lines with semi-ideal criteria
                for invoice_line in invoice_lines:
                    domain = self._build_payment_search_domain(
                        move,
                        invoice_line,
                        date_range={"date_from": date_from, "date_to": date_to},
                    )
                    # Add exact amount match for semi-ideal criteria
                    domain.append(
                        ("amount_residual", "=", -invoice_line.amount_residual)
                    )

                    payment_lines = self.env["account.move.line"].search(
                        domain, order="date asc, id asc", limit=1
                    )

                    if payment_lines:
                        # Perform reconciliation
                        (invoice_line + payment_lines).reconcile()
                        # Add post-message to invoice
                        move.message_post(
                            body=Markup(
                                self.env._(
                                    "Automatic reconciliation applied: <strong>Semi-Ideal</strong>"
                                    " - Same partner, exact amount, date within range"
                                )
                            ),
                            message_type="notification",
                        )
                        reconciled_count += 1

            except Exception as e:
                errors.append(self.env._("Error reconciling %s: %s", move.name, str(e)))

        # Prepare result message
        return self._prepare_reconciliation_result(
            reconciled_count, 0, errors, "Semi-Ideal"
        )

    def action_auto_reconcile_no_ideal(self):
        """Auto-reconcile using no-ideal criteria: same partner, exact amount, no date restriction (oldest payment first)."""
        reconciled_count = 0
        errors = []

        for move in self:
            try:
                # Validations
                if move.state != "posted":
                    errors.append(self.env._("Invoice %s is not posted", move.name))
                    continue

                if move.payment_state == "paid":
                    errors.append(self.env._("Invoice %s is already paid", move.name))
                    continue

                # Get receivable/payable lines with residual amount
                invoice_lines = self._get_invoice_reconcilable_lines(move)

                if not invoice_lines:
                    errors.append(
                        self.env._("Invoice %s has no lines to reconcile", move.name)
                    )
                    continue

                # Search for payment lines with no-ideal criteria (no date restriction)
                for invoice_line in invoice_lines:
                    domain = self._build_payment_search_domain(
                        move, invoice_line
                    )  # No date_range
                    # Add exact amount match for no-ideal criteria
                    domain.append(
                        ("amount_residual", "=", -invoice_line.amount_residual)
                    )
                    payment_line = self.env["account.move.line"].search(
                        domain,
                        order="date asc, id asc",
                        limit=1,  # Oldest payment first
                    )

                    if payment_line:
                        # Perform reconciliation
                        (invoice_line + payment_line).reconcile()
                        # Add post-message to invoice
                        move.message_post(
                            body=Markup(
                                self.env._(
                                    "Automatic reconciliation applied: <strong>No-Ideal</strong>"
                                    " - Same partner, exact amount, oldest payment (no date restriction)"
                                )
                            ),
                            message_type="notification",
                        )
                        reconciled_count += 1

            except Exception as e:
                errors.append(self.env._("Error reconciling %s: %s", move.name, str(e)))

        # Prepare result message
        return self._prepare_reconciliation_result(
            reconciled_count, 0, errors, "No-Ideal"
        )

    def action_auto_reconcile_multi_payment(self):
        """Auto-reconcile using multi-payment criteria: find combinations of payments that sum to invoice amount."""

        reconciled_count = 0
        errors = []

        for move in self:
            try:
                # Validations
                if move.state != "posted":
                    errors.append(self.env._("Invoice %s is not posted", move.name))
                    continue

                if move.payment_state == "paid":
                    errors.append(self.env._("Invoice %s is already paid", move.name))
                    continue

                # Get receivable/payable lines with residual amount
                invoice_lines = self._get_invoice_reconcilable_lines(move)

                if not invoice_lines:
                    errors.append(
                        self.env._("Invoice %s has no lines to reconcile", move.name)
                    )
                    continue

                # Calculate date range (1 month before to 2 months after)
                invoice_date = move.invoice_date
                date_from = invoice_date - timedelta(days=30)  # 1 month before
                date_to = invoice_date + timedelta(days=60)  # 2 months after

                for invoice_line in invoice_lines:
                    target_amount = abs(invoice_line.amount_residual)

                    # Search for all potential payment lines
                    domain = self._build_payment_search_domain(
                        move,
                        invoice_line,
                        date_range={"date_from": date_from, "date_to": date_to},
                    )

                    payment_lines = self.env["account.move.line"].search(
                        domain, order="date asc, id asc"
                    )

                    if not payment_lines:
                        continue

                    # Try combinations of payments to match the invoice amount
                    payment_amounts = [
                        (line, abs(line.amount_residual)) for line in payment_lines
                    ]

                    # Try combinations from size 1 to min(5, len(payment_amounts))
                    max_combination_size = min(5, len(payment_amounts))
                    valid_combinations = []

                    # Find all valid combinations first (including single payments)
                    valid_combinations = self._find_payment_combinations(
                        payment_amounts, target_amount, max_combination_size
                    )

                    # If valid combinations found, select the best one (prefer fewer payments, then oldest)
                    if valid_combinations:
                        # Sort by: 1) fewer payments first, 2) oldest date first
                        valid_combinations.sort(
                            key=lambda x: (x["size"], x["oldest_date"])
                        )
                        best_combination = valid_combinations[0]

                        # Perform reconciliation with the best combination
                        lines_to_reconcile = invoice_line + self.env[
                            "account.move.line"
                        ].browse([line.id for line in best_combination["lines"]])
                        lines_to_reconcile.reconcile()
                        # Add post-message to invoice
                        move.message_post(
                            body=Markup(
                                self.env._(
                                    "Automatic reconciliation applied: <strong>Multi-Payment</strong>"
                                    " - Combined %s payments to match invoice amount",
                                    len(best_combination["lines"]),
                                )
                            ),
                            message_type="notification",
                        )
                        reconciled_count += 1

            except Exception as e:
                errors.append(self.env._("Error reconciling %s: %s", move.name, str(e)))

        # Prepare result message
        return self._prepare_reconciliation_result(
            reconciled_count, 0, errors, "Multi-Payment"
        )

    def _find_payment_combinations(
        self, payment_amounts, target_amount, max_combination_size
    ):
        """Find valid payment combinations that match the target amount."""
        valid_combinations = []

        for combination_size in range(1, max_combination_size + 1):
            for combo in combinations(payment_amounts, combination_size):
                combo_lines = [item[0] for item in combo]
                combo_sum = sum(item[1] for item in combo)

                # Check if combination sum matches target amount (with small tolerance)
                if abs(combo_sum - target_amount) < 0.01:
                    # Calculate oldest date in this combination
                    combo_dates = [line.date for line in combo_lines]
                    oldest_date = min(combo_dates)

                    valid_combinations.append(
                        {
                            "lines": combo_lines,
                            "sum": combo_sum,
                            "size": len(combo_lines),
                            "oldest_date": oldest_date,
                        }
                    )

        return valid_combinations

    def action_auto_reconcile_partial(self):
        """Auto-reconcile using improved partial criteria: apply all available payments
        sequentially from oldest to newest until invoice is fully paid or no more payments available.

        This method removes date restrictions and applies payments chronologically to ensure
        maximum reconciliation coverage.
        """
        reconciled_count = 0
        partially_reconciled_count = 0
        errors = []

        # Process invoices by age (oldest first)
        moves_by_age = self.sorted(lambda m: m.invoice_date or m.date)

        for move in moves_by_age:
            
            try:
                # Validations
                if move.state != "posted":
                    errors.append(self.env._("Invoice %s is not posted", move.name))
                    continue

                if move.payment_state == "paid":
                    continue  # Skip already paid invoices

                # Get receivable/payable lines with residual amount
                invoice_lines = self._get_invoice_reconcilable_lines(move)

                if not invoice_lines:
                    continue

                # Track if any reconciliation occurred for this invoice
                invoice_reconciled = False
                payments_applied = []
                total_applied_amount = 0

                for invoice_line in invoice_lines:
                    # Continue applying payments until this invoice line is fully reconciled
                    # or no more suitable payments are available

                    while (
                        abs(invoice_line.amount_residual) > 0.01
                    ):  # Continue until fully paid
                        # Search for ALL available payment lines from same partner (no date restrictions)
                        domain = self._build_payment_search_domain(
                            move, invoice_line
                        )  # No date_range

                        # Get oldest available payment first
                        payment_line = self.env["account.move.line"].search(
                            domain,
                            order="date asc, id asc",
                            limit=1,  # Oldest payment first
                        )

                        if not payment_line:
                            # No more payments available for this partner
                            break

                        # Apply this payment to the invoice
                        payment_amount = abs(payment_line.amount_residual)
                        remaining_invoice_amount = abs(invoice_line.amount_residual)

                        # Perform reconciliation between invoice line and payment line
                        (invoice_line + payment_line).reconcile()

                        # Track the payment application
                        payments_applied.append(
                            {
                                "payment_ref": payment_line.move_id.name
                                or payment_line.name,
                                "amount": min(payment_amount, remaining_invoice_amount),
                                "date": payment_line.date,
                            }
                        )
                        total_applied_amount += min(
                            payment_amount, remaining_invoice_amount
                        )
                        invoice_reconciled = True

                        # Refresh the invoice line to get updated residual
                        invoice_line.invalidate_recordset(["amount_residual"])

                # Post appropriate message based on reconciliation result
                if invoice_reconciled:
                    # Check if invoice is now fully paid
                    move.invalidate_recordset(["payment_state", "amount_residual"])

                    if move.payment_state == "paid" or abs(move.amount_residual) < 0.01:
                        # Invoice fully reconciled
                        message_body = self.env._(
                            "Automatic reconciliation applied: <strong>Partial (Complete)</strong><br/>"
                            "Applied %s payment(s) totaling %.2f from oldest to newest:<br/>",
                            len(payments_applied),
                            total_applied_amount,
                        )

                        # Add payment details
                        for payment in payments_applied:
                            message_body += self.env._(
                                "• %s: %.2f (Date: %s)<br/>",
                                payment["payment_ref"],
                                payment["amount"],
                                payment["date"],
                            )

                        move.message_post(
                            body=Markup(message_body), message_type="notification"
                        )
                        reconciled_count += 1
                    else:
                        # Invoice partially reconciled
                        message_body = self.env._(
                            "Automatic reconciliation applied: <strong>Partial (Incomplete)</strong><br/>"
                            "Applied %s payment(s) totaling %.2f, remaining balance: %.2f<br/>",
                            len(payments_applied),
                            total_applied_amount,
                            abs(move.amount_residual),
                        )

                        # Add payment details
                        for payment in payments_applied:
                            message_body += self.env._(
                                "• %s: %.2f (Date: %s)<br/>",
                                payment["payment_ref"],
                                payment["amount"],
                                payment["date"],
                            )

                        move.message_post(
                            body=Markup(message_body), message_type="notification"
                        )
                        partially_reconciled_count += 1

            except Exception as e:
                errors.append(self.env._("Error reconciling %s: %s", move.name, str(e)))

        # Prepare result message
        return self._prepare_reconciliation_result(
            reconciled_count, partially_reconciled_count, errors, "Enhanced Partial"
        )
