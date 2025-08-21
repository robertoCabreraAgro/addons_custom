import logging

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ApprovalRequest(models.Model):
    _inherit = "approval.request"

    telegram_data = fields.Json(string="Telegram Data (JSON)")
    telegram_data_formatted = fields.Html(
        string="Telegram Data (Formatted)",
        compute="_compute_telegram_data_formatted",
        readonly=True,
    )

    has_bsl = fields.Selection(related="category_id.has_bsl")
    has_operation_type = fields.Selection(related="category_id.has_operation_type")

    used_bank_statement_line_ids = fields.Many2many(
        comodel_name="account.bank.statement.line",
        compute="_compute_used_bank_statement_line_ids",
        string="Used Bank Statement Lines",
        help="Bank statement lines already used in other approval requests.",
    )

    bank_statement_date_to = fields.Date(
        string="Bank Statement Date To",
        compute="_compute_bank_statement_date_to",
        help="End date for bank statement line search based on payment method.",
    )
    bank_statement_line_id = fields.Many2one(
        comodel_name="account.bank.statement.line",
        string="Bank Statement Line",
        domain="[('date', '>=', date), ('date', '<=', bank_statement_date_to), ('amount', '=', amount), ('is_reconciled', '=', False), ('id', 'not in', used_bank_statement_line_ids)]",
        help="Select the bank transaction that corresponds to this payment.",
    )
    operation_type_id = fields.Many2one(
        comodel_name="account.move.operation.type",
        string="Operation Type",
        help="Select the type of accounting operation to generate.",
    )
    account_move_operation_id = fields.Many2one(
        comodel_name="account.move.operation",
        string="Accounting Operation",
        readonly=True,
        copy=False,
    )

    def _compute_used_bank_statement_line_ids(self):
        """Compute bank statement lines already used in other approval requests."""
        for record in self:
            domain = [("bank_statement_line_id", "!=", False)]
            if record.id:
                # Exclude current record if it exists
                domain.append(("id", "!=", record.id))

            used_approvals = self.search(domain)
            used_lines = used_approvals.mapped("bank_statement_line_id")
            record.used_bank_statement_line_ids = used_lines

    @api.depends("date", "telegram_data")
    def _compute_bank_statement_date_to(self):
        """Compute end date for bank statement search based on payment method."""
        for record in self:
            if not record.date:
                record.bank_statement_date_to = False
                continue

            # Get payment method from telegram_data
            payment_method = ""
            if record.telegram_data:
                payment_method = record.telegram_data.get("payment_method", "")

            # For card (TC, TD), allow up to 7 days after the payment date
            if payment_method == "TC" or payment_method == "TD":
                record.bank_statement_date_to = fields.Date.add(record.date, days=7)
            else:
                # For other payment methods, use the same date
                record.bank_statement_date_to = record.date

    @api.depends("telegram_data")
    def _compute_telegram_data_formatted(self):
        """Formats the JSON data into a human-readable HTML block."""
        for request in self:
            if not request.telegram_data:
                request.telegram_data_formatted = False
                continue

            data = request.telegram_data

            # Define labels in the desired order
            labels = {
                "partner_fx_name": "A quién se factura",
                "product_category": "Categoría de producto",
                "cfdi_use": "Uso CFDI",
                "company": "Compañía",
                "partner_cn_name": "A quién se aplica el pago",
                "payment_method": "Método de pago",
                "date": "Fecha de pago",
                "amount": "Monto",
            }

            # Build an HTML table for a clean, aligned layout
            html_rows = ""
            for key, label in labels.items():
                value = data.get(key, "N/A")
                html_rows += f"""
                    <tr>
                        <td style="padding: 4px; font-weight: bold;">{label}</td>
                        <td style="padding: 4px;">{value}</td>
                    </tr>
                """

            # Using Markup is important to prevent Odoo from escaping the HTML.
            request.telegram_data_formatted = Markup(
                f"""
                <div style="font-family: sans-serif; font-size: 14px;">
                    <table class="o_list_table table table-sm table-hover">
                        <tbody>
                            {html_rows}
                        </tbody>
                    </table>
                </div>
            """
            )

    def _create_accounting_operation(self):
        """Uses the wizard 'account.move.operation.from.entry' to create
        and link an accounting operation.
        """
        self.ensure_one()
        if not self.bank_statement_line_id or not self.operation_type_id:
            raise UserError(
                _(
                    "Please select a Bank Statement Line and an Operation Type before creating the operation."
                )
            )

        wizard_model = self.env["account.move.operation.from.entry"]

        # Get currency from the bank statement line, its journal, or the company as a fallback
        currency = (
            self.bank_statement_line_id.currency_id
            or self.bank_statement_line_id.journal_id.currency_id
            or self.company_id.currency_id
        )

        # Prepare values to create the wizard record.
        # This mimics a user filling the form before clicking the button.
        wizard_vals = {
            "st_line_id": self.bank_statement_line_id.id,
            "operation_type_id": self.operation_type_id.id,
            "partner_id": self.partner_id.id,
            "amount": abs(self.bank_statement_line_id.amount),
            "currency_id": currency.id,
            "company_id": self.company_id.id,
        }
        wizard = wizard_model.create(wizard_vals)

        # Trigger the onchange method to populate action lines in the wizard.
        # This is a crucial step that was missing full context before.
        wizard._onchange_operation_type_id()

        # Execute the main action of the wizard, which creates the operation
        # and returns a window action dictionary.
        action_result = wizard.action_create_operation()

        # The created record's ID is in the 'res_id' of the returned action.
        created_op_id = (
            action_result.get("res_id") if isinstance(action_result, dict) else None
        )

        if not created_op_id:
            _logger.error(
                "Wizard 'action_create_operation' did not return a valid res_id for approval %s.",
                self.name,
            )
            raise UserError(
                _(
                    "Operation creation failed. The wizard did not return the created record. Please check the logs."
                )
            )

        self.account_move_operation_id = created_op_id
        _logger.info(
            "Successfully created and linked operation (ID: %s) for approval %s.",
            created_op_id,
            self.name,
        )

    def action_approve(self, approver=None):
        """Extend the approval action to create the accounting operation if needed."""
        res = super().action_approve(approver=approver)
        for request in self:
            # Check if this is the final approval
            if request.has_operation_type != "no" and request.has_bsl != "no":
                request._create_accounting_operation()
                request.bank_statement_line_id.partner_id = request.partner_id
        return res
