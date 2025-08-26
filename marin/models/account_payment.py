from markupsafe import Markup

from odoo import api, fields, models
from odoo.tools.translate import _


class AccountPayment(models.Model):
    """Inherit AccountPayment"""

    _inherit = "account.payment"

    journal_type = fields.Selection(
        related="journal_id.type",
        string="Journal type",
        store=True,
        readonly=True,
    )

    @api.depends("company_id", "journal_id", "partner_id", "partner_type")
    def _compute_destination_account_id(self):
        self.destination_account_id = False
        for pay in self:
            accounts = self._get_destination_accounts()
            if pay.partner_type == "customer":
                pay.destination_account_id = accounts.get("customer") or self.env[
                    "account.account"
                ].with_company(pay.company_id).search(
                    [
                        *self.env["account.account"]._check_company_domain(
                            pay.company_id
                        ),
                        ("deprecated", "=", False),
                        ("account_type", "=", "asset_receivable"),
                    ],
                    limit=1,
                )
            elif pay.partner_type == "supplier":
                pay.destination_account_id = accounts.get("supplier") or self.env[
                    "account.account"
                ].with_company(pay.company_id).search(
                    [
                        *self.env["account.account"]._check_company_domain(
                            pay.company_id
                        ),
                        ("deprecated", "=", False),
                        ("account_type", "=", "liability_payable"),
                    ],
                    limit=1,
                )

    def _get_destination_accounts(self):
        return {
            "customer": self.partner_id.with_company(
                self.company_id
            ).property_account_receivable_id
            or self.journal_id.default_receivable_account_id,
            "supplier": self.partner_id.with_company(
                self.company_id
            ).property_account_payable_id
            or self.journal_id.default_payable_account_id,
        }

    # -------------------------------------------------------------------------
    # RECONCILIATION METHODS (Task 10105)
    # -------------------------------------------------------------------------

    def action_auto_reconcile_multi_invoice(self):
        """Auto-reconcile using multi-invoice criteria: find combinations of invoices that sum to payment amount."""
        from itertools import combinations

        reconciled_count = 0
        errors = []

        for payment in self:
            try:
                # Validations
                if payment.state != "paid":
                    errors.append(_("Payment %s is not in paid state") % payment.name)
                    continue

                if payment.is_reconciled:
                    errors.append(_("Payment %s is already reconciled") % payment.name)
                    continue

                # Get the payment's move line in receivable/payable account
                account_type = (
                    "asset_receivable"
                    if payment.partner_type == "customer"
                    else "liability_payable"
                )
                payment_lines = payment.move_id.line_ids.filtered(
                    lambda l: l.account_id.account_type == account_type
                    and l.amount_residual != 0
                )

                if not payment_lines:
                    errors.append(
                        _("Payment %s has no lines to reconcile") % payment.name
                    )
                    continue

                for payment_line in payment_lines:
                    target_amount = abs(payment_line.amount_residual)

                    # Search for invoice lines with residual amounts (same partner, no date restriction)
                    domain = [
                        ("account_id.account_type", "=", account_type),
                        ("partner_id", "=", payment.partner_id.id),
                        ("reconciled", "=", False),
                        ("parent_state", "=", "posted"),
                        ("id", "!=", payment_line.id),  # Not the same line
                    ]

                    # Filter invoice lines that have opposite sign
                    if payment_line.amount_residual > 0:  # Debit payment (supplier)
                        domain.append(("amount_residual", "<", 0))  # Credit invoices
                    else:  # Credit payment (customer)
                        domain.append(("amount_residual", ">", 0))  # Debit invoices

                    invoice_lines = self.env["account.move.line"].search(
                        domain, order="date asc, id asc"
                    )

                    if not invoice_lines:
                        continue

                    # Try combinations of invoices to match the payment amount
                    invoice_amounts = [
                        (line, abs(line.amount_residual)) for line in invoice_lines
                    ]

                    # Try combinations from size 1 to min(10, len(invoice_amounts))
                    max_combination_size = min(10, len(invoice_amounts))
                    found_combination = False

                    # First try single invoice match
                    for invoice_line, invoice_amount in invoice_amounts:
                        if abs(invoice_amount - target_amount) < 0.01:
                            # Exact single match
                            lines_to_reconcile = payment_line + invoice_line
                            lines_to_reconcile.reconcile()
                            # Add post-message to invoice
                            invoice_line.move_id.message_post(
                                body=Markup(
                                    _(
                                        "Automatic reconciliation applied: <strong>Multi-Invoice (Single)</strong> - Payment matched exactly to this invoice"
                                    )
                                ),
                                message_type="notification",
                            )
                            reconciled_count += 1
                            found_combination = True
                            break

                    if found_combination:
                        continue

                    # Try combinations of multiple invoices
                    for r in range(2, max_combination_size + 1):
                        if found_combination:
                            break

                        for combo in combinations(invoice_amounts, r):
                            combo_lines = [item[0] for item in combo]
                            combo_sum = sum(item[1] for item in combo)

                            # Check if combination sum matches target amount (with small tolerance)
                            if abs(combo_sum - target_amount) < 0.01:
                                # Perform reconciliation
                                lines_to_reconcile = payment_line + self.env[
                                    "account.move.line"
                                ].browse([l.id for l in combo_lines])
                                lines_to_reconcile.reconcile()
                                # Add post-message to each reconciled invoice
                                for combo_line in combo_lines:
                                    combo_line.move_id.message_post(
                                        body=Markup(
                                            _(
                                                "Automatic reconciliation applied: <strong>Multi-Invoice</strong> - Combined with %d other invoices for payment matching"
                                            )
                                            % (len(combo_lines) - 1)
                                        ),
                                        message_type="notification",
                                    )
                                reconciled_count += 1
                                found_combination = True
                                break

            except Exception as e:
                errors.append(
                    _("Error reconciling payment %s: %s") % (payment.name, str(e))
                )

        # Prepare result message
        if reconciled_count > 0:
            message = (
                _("%d payment(s) reconciled successfully with multiple invoices.")
                % reconciled_count
            )
        else:
            message = _("No payments could be reconciled with multi-invoice criteria.")

        if errors:
            message += "\n\n" + _("Errors:") + "\n" + "\n".join(errors)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Auto Reconciliation - Multi-Invoice"),
                "message": message,
                "type": "success" if reconciled_count > 0 else "warning",
                "sticky": True,
            },
        }
