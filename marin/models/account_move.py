from werkzeug.urls import url_quote_plus

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_round
from odoo.tools.misc import formatLang


class AccountMove(models.Model):
    _inherit = "account.move"

    # Extended fields
    date = fields.Date(copy=True)
    invoice_date = fields.Date(copy=True)
    invoice_origin = fields.Char(readonly=False)
    l10n_mx_edi_payment_policy = fields.Selection(store=True, readonly=False)
    l10n_mx_edi_usage = fields.Selection(selection_add=[("CP01", "Payments")])
    document_share_id = fields.Many2one("documents.share", readonly=True)

    # New fields
    journal_type = fields.Selection(related="journal_id.type", string="Journal type", store=True, readonly=True)
    x_check_tax = fields.Monetary(
        "Verification tax",
        copy=False,
    )
    x_check_total = fields.Monetary(
        "Verification total",
        copy=False,
    )
    x_tax_difference = fields.Monetary("Tax difference", compute="_compute_x_difference")
    x_total_difference = fields.Monetary("Total difference", compute="_compute_x_difference")
    force_payment_policy_pue = fields.Boolean("Force PUE")
    relate_purchase_order = fields.Boolean()
    related_purchase_order_id = fields.Many2one("purchase.order", readonly=True)
    x_stored = fields.Boolean(
        "Stored",
        tracking=True,
        help="If this checkbox is ticked, it means that a management representative has "
        "received and stored a printed invoice on credit signed by the customer. ",
    )

    def action_open_move_lines(self):
        return {
            "name": _("Move Lines"),
            "type": "ir.actions.act_window",
            "res_model": "account.move.line",
            "view_mode": "list",
            "views": [(self.env.ref("account.view_move_line_tree").id, "tree"), (False, "form")],
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

    @api.depends("amount_tax", "amount_total", "x_check_tax", "x_check_total")
    def _compute_x_difference(self):
        for move in self:
            move.x_tax_difference = 0.0
            move.x_total_difference = 0.0
            if move.x_check_tax:
                move.x_tax_difference = float_round(
                    move.x_check_tax - move.amount_tax, precision_rounding=move.currency_id.rounding
                )
            if move.x_check_total:
                move.x_total_difference = float_round(
                    move.x_check_total - move.amount_total, precision_rounding=move.currency_id.rounding
                )

    # Override original method
    @api.depends("company_id", "currency_id", "partner_id", "amount_total")
    def _compute_partner_credit_warning(self):
        for invoice in self:
            invoice.with_company(invoice.company_id)
            invoice.partner_credit_warning = ""
            amount_total_currency = (
                invoice.currency_id._convert(
                    invoice.amount_total, invoice.company_currency_id, invoice.company_id, invoice.date
                )
                if invoice.move_type == "out_invoice"
                else 0
            )
            show_warning = (
                invoice.company_id.account_use_credit_limit
                and invoice.state == "draft"
                and invoice.commercial_partner_id
                and invoice.commercial_partner_id.credit_limit_available < amount_total_currency
            )
            if show_warning:
                future_credit = invoice.commercial_partner_id.credit + amount_total_currency
                invoice.partner_credit_warning = invoice.commercial_partner_id._build_credit_warning_message(
                    future_credit, invoice.company_id.currency_id
                )

    def _pre_post_invoice_edi_amounts_match_validation(self):
        for invoice in self.filtered(lambda i: i.is_invoice()):
            if (invoice.x_check_tax or invoice.x_check_total) and (
                float_compare(
                    invoice.x_check_total, invoice.amount_total, precision_rounding=invoice.currency_id.rounding
                )
                or float_compare(
                    invoice.x_check_tax, invoice.amount_tax, precision_rounding=invoice.currency_id.rounding
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
            if authorized or self.env["ir.config_parameter"].sudo().get_param("marin.avoid_authorize_debt"):
                return True
            return invoice.action_authorize_debt_wizard()
        return True

    # Extend original method
    def unlink(self):
        cancelled_moves = self.env["account.move"]
        if self.env.user.has_group("marin.group_account_move_force_removal"):
            cancelled_moves |= self.filtered(lambda m: m.state == "cancel")
            super(AccountMove, cancelled_moves.with_context(force_delete=True)).unlink()
        return super(AccountMove, self - cancelled_moves).unlink()

    # Extend original method
    def action_post(self):
        folder = self.env.ref("documents.documents_finance_folder")
        self._pre_post_invoice_edi_amounts_match_validation()
        res = self._pre_post_invoice_credit_limit_validation()
        if res is not True:
            return res
        for rec in self:
            if rec.move_type in ["out_invoice", "out_refund"] and not rec.document_share_id:
                self.document_share_id = self.env["documents.share"].create(
                    {
                        "type": "ids",
                        "name": "share_link_ids",
                        "folder_id": folder.id,
                    }
                )
        return super().action_post()

    def button_draft(self):
        for move in self:
            move.mapped("line_ids.fleet_vehicle_log_services_ids").unlink()
        return super().button_draft()

    def button_set_stored(self):
        for move in self:
            move.stored = True

    def _prepare_purchase_order_vals(self):
        self.ensure_one()
        return {
            "company_id": self.company_id.id,
            "currency_id": self.currency_id.id,
            "partner_id": self.commercial_partner_id.id,
            "dest_address_id": False,  # False since only supported in stock
            "date_order": self.invoice_date,
            "fiscal_position_id": (
                self.fiscal_position_id or self.fiscal_position_id._get_fiscal_position(self.commercial_partner_id)
            ).id,
            "payment_term_id": self.invoice_payment_term_id.id,
            "origin": self.name,
            "invoice_status": "invoiced",
        }

    def _prepare_purchase_line_vals(self, move, purchase):
        self.ensure_one()
        purchase_line_vals = {}
        fpos = purchase.fiscal_position_id
        for line in move.invoice_line_ids.filtered(lambda ln: ln.display_type == "product"):
            taxes = fpos.map_tax(line.product_id.supplier_taxes_id)
            if taxes:
                taxes = taxes.filtered(lambda t: t.company_id.id == self.company_id.id)
            purchase_line_vals[line.id] = {
                "order_id": purchase.id,
                "product_id": line.product_id.id,
                "name": "[%s] %s" % (line.product_id.default_code, line.name)
                if line.product_id.default_code
                else line.name,
                "product_qty": line.quantity,
                "product_uom": line.product_uom_id.id,
                "price_unit": line.price_unit,
                "date_planned": fields.Date.from_string(purchase.date_order),
                "taxes_id": [Command.set(taxes.ids)],
                "analytic_distribution": line.analytic_distribution,
            }
        return purchase_line_vals

    def create_purchase_order(self):
        for move in self:
            if any(not line.product_id for line in move.invoice_line_ids):
                raise UserError(_("Some move lines does not have a product set. Please review"))
            purchase_exist = self.env["purchase.order"].search(
                [
                    ("partner_id", "=", self.commercial_partner_id.id),
                    ("company_id", "=", self.company_id.id),
                    ("origin", "=", self.name),
                ]
            )
            if purchase_exist and len(purchase_exist) >= 1:
                raise UserError(_("More than one Purchase Orders with the same origin have been found. Please review"))
            if not purchase_exist:
                purchase_exist = self.env["purchase.order"].create(self._prepare_purchase_order_vals())
                purchase_line_vals = self._prepare_purchase_line_vals(move, purchase_exist)
                for line, vals in purchase_line_vals.items():
                    move_line = self.env["account.move.line"].browse(int(line))
                    po_line = self.env["purchase.order.line"].create(vals)
                    move_line.purchase_line_id = po_line.id
            move._compute_origin_po_count()
        return True

    # Extend original method
    @api.depends("company_currency_id", "journal_id", "move_type", "payment_id", "statement_line_id")
    def _compute_l10n_mx_edi_is_cfdi_needed(self):
        """Check whatever or not the CFDI is needed on this invoice."""
        for move in self:
            move.l10n_mx_edi_is_cfdi_needed = (
                move.country_code == "MX"
                and move.company_currency_id.name == "MXN"
                and move.journal_id.x_treatment in ("fiscal_simulated", "fiscal_real")
                and (move.move_type in ("out_invoice", "out_refund") or move._l10n_mx_edi_is_cfdi_payment())
            )

    # Extend original method
    @api.depends(
        "move_type", "invoice_date_due", "invoice_date", "invoice_payment_term_id", "force_payment_policy_pue"
    )
    def _compute_l10n_mx_edi_payment_policy(self):
        for move in self:
            if (
                move.is_invoice(include_receipts=True)
                and move.l10n_mx_edi_is_cfdi_needed
                and move.invoice_date_due
                and move.invoice_date
            ):
                move.l10n_mx_edi_payment_policy = "PUE"
                if (
                    move.move_type == "out_invoice"
                    and not move.l10n_mx_edi_cfdi_to_public
                    and (
                        move.invoice_date_due.month > move.invoice_date.month
                        or move.invoice_date_due.year > move.invoice_date.year
                        # This is not always true
                        # or len(move.invoice_payment_term_id.line_ids) > 1
                    )
                ):
                    move.l10n_mx_edi_payment_policy = "PPD"
            if move.l10n_mx_edi_payment_policy and move.force_payment_policy_pue:
                move.l10n_mx_edi_payment_policy = "PUE"

    def _compute_name(self):
        self._compute_name_by_sequence()

    @api.onchange("purchase_vendor_bill_id", "purchase_id")
    def _onchange_purchase_auto_complete(self):
        if not self.relate_purchase_order:
            return super()._onchange_purchase_auto_complete()
        self.related_purchase_order_id = self.purchase_vendor_bill_id.purchase_order_id
        self.purchase_vendor_bill_id = False
        self._relate_with_purchase_lines()

    def _relate_with_purchase_lines(self):
        if not self.related_purchase_order_id:
            return
        purchase = self.related_purchase_order_id
        for record in self.invoice_line_ids.filtered(lambda l: not l.purchase_line_id and l.product_id):
            prod = record.product_id
            lines = purchase.mapped("order_line").filtered(lambda p: p.product_id == prod)
            if not lines:
                continue
            record.purchase_line_id = record._get_po_line_candidate(lines)

    def _generate_document_from_report(self, report_content):
        doc_name = _("Credit Note %s", self.name) if self.move_type == "out_refund" else _("Invoice %s", self.name)
        folder = self.env.ref("documents.documents_finance_folder")
        attachment = self.env["ir.attachment"].create(
            {
                "name": doc_name,
                "raw": report_content,
                "mimetype": "application/pdf",
            }
        )
        vals = {
            "folder_id": folder.id,
            "name": doc_name,
            "attachment_id": attachment.id,
        }
        self.document_share_id.document_ids.attachment_id.unlink()
        self.document_share_id.document_ids.unlink()
        self.document_share_id.write({"document_ids": [(0, 0, vals)]})

    def _is_valid_generate_document_from_report(self):
        return self and len(self) == 1 and self.document_share_id and self.move_type in ["out_invoice", "out_refund"]

    def _get_invoice_qr(self):
        barcode_value = url_quote_plus(self.document_share_id.full_url)
        barcode_src = f"/report/barcode/?barcode_type=QR&value={barcode_value}&width=120&height=120"
        return barcode_src
