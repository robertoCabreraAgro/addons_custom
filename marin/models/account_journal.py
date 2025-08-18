import base64

from odoo import api, Command, fields, models, tools
from odoo.exceptions import UserError, RedirectWarning
from odoo.tools.translate import _


class AccountJournal(models.Model):
    """Inherit AccountJournal"""

    _inherit = "account.journal"

    default_receivable_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Default Receivable Account",
        check_company=True,
        domain=[("active", "=", True), ("account_type", "=", "asset_receivable")],
        copy=False,
        ondelete="restrict",
        help="It acts as a default account for receivable amount instead of the Company's default",
    )
    default_payable_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Default Payable Account",
        check_company=True,
        domain=[("active", "=", True), ("account_type", "=", "liability_payable")],
        copy=False,
        ondelete="restrict",
        help="It acts as a default account for payable amount instead of the Company's default",
    )
    default_refund_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Default Refund Account",
        check_company=True,
        domain=[
            ("active", "=", True),
            (
                "account_type",
                "in",
                ("expense", "expense_direct_cost", "income", "income_other"),
            ),
        ],
        copy=False,
        ondelete="restrict",
        help="It acts as a default account for refunds",
    )
    x_treatment = fields.Selection(
        [
            ("not_fiscal_simulated", "Not Fiscal simulated"),
            ("not_fiscal_real", "Not Fiscal real"),
            ("fiscal_simulated", "Fiscal simulated"),
            ("fiscal_real", "Fiscal real"),
        ],
        string="Treatment",
        default="not_fiscal_real",
        help="Technical field used to group journal and journal moves according to fiscal logic.",
    )
    account_control_ids = fields.Many2many(
        "account.account",
        "account_journal_account_account_control_rel",
        "journal_id",
        "account_id",
        string="Allowed accounts",
        check_company=True,
        domain=[("active", "=", True), ("account_type", "!=", "off_balance")],
    )
    user_can_access_ids = fields.Many2many(
        "res.users",
        "account_journal_res_users_can_access_rel",
        "journal_id",
        "user_id",
        string="Allowed users",
        help="Users that can visualize entries of this journal.",
    )

    @api.constrains(
        "type", "default_receivable_account_id", "default_payable_account_id"
    )
    def _check_type_default_receivable_payable_account_id_type(self):
        journals_to_check = self.filtered(
            lambda journal: journal.type in ("sale", "purchase")
        )
        accounts_to_check = journals_to_check.mapped(
            "default_receivable_account_id"
        ) + journals_to_check.mapped("default_payable_account_id")
        if any(
            account.account_type not in ("asset_receivable", "liability_payable")
            for account in accounts_to_check
        ):
            raise UserError(
                _(
                    "The type of the journal's default receivable/payable "
                    'account should be "receivable" or "payable".'
                )
            )

    def _is_bbva_mx(self):
        return self.bank_id == self.env.ref("l10n_mx.acc_bank_012_BBVA_BANCOMER")

    def _check_bbva_mx_attachment(self, attachment):
        self.ensure_one()
        if self._is_bbva_mx():
            file_content = base64.b64decode(attachment.datas)
            file_name = attachment.name.lower().strip()
            if file_name.endswith(".txt"):
                return self.env["bbva.parser"]._validate_header(
                    file_content, file_type="txt"
                )
            elif file_name.endswith((".xls", ".xlsx")):
                return self.env["bbva.parser"]._validate_header(
                    file_content, file_type="xlsx"
                )
        return False

    def _import_bbva_mx_bank_statement(self, attachments):
        if any(not a.raw for a in attachments):
            raise UserError(_("You uploaded an invalid or empty file."))

        if len(attachments) > 1:
            raise UserError(
                _(
                    f"Only one TXT o XLSX file can be selected for a {self.bank_id.name} Journal"
                )
            )
        bank_statement = self.env["account.bank.statement"]
        bank_statement_line = self.env["account.bank.statement.line"]
        statement_ids_all = []
        notifications_all = {}
        errors = {}
        # Let the appropriate implementation module parse the file and return the required data
        # The active_id is passed in context in case an implementation module requires information about the wizard state (see QIF)
        for attachment in attachments:
            try:
                (
                    currency_code,
                    account_number,
                    stmts_vals,
                ) = self._parse_bank_statement_file(attachment)
                # Check raw data
                self._check_parsed_data(stmts_vals, account_number)
                # Try to find the currency and journal in odoo
                if not self.default_account_id:
                    raise UserError(
                        _(
                            "You have to set a Default Account for the journal: %s",
                            self.name,
                        )
                    )

                st_vals = stmts_vals[0]
                statement_name = st_vals.get("name") or st_vals.get("reference")

                # Find existing statement for BBVA
                existing_statement = bank_statement.search(
                    [
                        ("journal_id", "=", self.id),
                        ("name", "=", statement_name),
                    ],
                    limit=1,
                )

                statement_ids = existing_statement.ids
                notifications = []

                if not existing_statement:
                    # Create the bank statements
                    statement_ids, dummy, notifications = self._create_bank_statements(
                        stmts_vals
                    )
                else:
                    # Process transactions for existing statement
                    filtered_lines = []
                    ignored_ids = []

                    for line_vals in st_vals.get("transactions", []):
                        # Skip zero-amount or duplicate transactions
                        if line_vals["amount"] == 0:
                            continue

                        unique_id = line_vals.get("unique_import_id")
                        if unique_id and bank_statement_line.search_count(
                            [("unique_import_id", "=", unique_id)]
                        ):
                            ignored_ids.append(unique_id)
                            if "balance_start" in st_vals:
                                st_vals["balance_start"] += float(line_vals["amount"])
                            continue
                        filtered_lines.append(line_vals)

                    # Update existing statement
                    existing_statement.write(
                        {
                            "line_ids": [
                                Command.create(vals) for vals in filtered_lines
                            ],
                            "date": st_vals["date"],
                        }
                    )

                    # Prepare notifications for ignored transactions
                    if ignored_ids:
                        msg = (
                            (
                                _("%d transactions were ignored as duplicates")
                                % len(ignored_ids)
                            )
                            if len(ignored_ids) > 1
                            else _("1 duplicate transaction was ignored")
                        )
                        notifications.append({"type": "warning", "message": msg})

                statement_ids_all.extend(statement_ids)

                # Now that the import worked out, set it as the bank_statements_source of the journal
                if self.bank_statements_source != "file_import":
                    # Use sudo() because only 'account.group_account_manager'
                    # has write access on 'account.journal', but 'account.group_account_user'
                    # must be able to import bank statement files
                    self.sudo().bank_statements_source = "file_import"

                msg = ""
                for notif in notifications:
                    msg += f"{notif['message']}"
                if notifications:
                    notifications_all[attachment.name] = msg
            except (UserError, RedirectWarning) as e:
                errors[attachment.name] = e.args[0]

        statements = bank_statement.browse(statement_ids_all)
        line_to_reconcile = statements.line_ids
        if line_to_reconcile:
            # 'limit_time_real_cron' defaults to -1.
            # Manual fallback applied for non-POSIX systems where this key is disabled (set to None).
            cron_limit_time = tools.config["limit_time_real_cron"] or -1
            limit_time = cron_limit_time if 0 < cron_limit_time < 180 else 180
            line_to_reconcile._cron_try_auto_reconcile_statement_lines(
                limit_time=limit_time
            )

        result = bank_statement_line._action_open_bank_reconciliation_widget(
            extra_domain=[("statement_id", "in", statements.ids)],
            default_context={
                "search_default_not_matched": True,
                "default_journal_id": statements[:1].journal_id.id,
                "notifications": notifications_all,
            },
        )

        if errors:
            error_msg = _("The following files could not be imported:\n")
            error_msg += "\n".join(
                [
                    f"- {attachment_name} →  {msg}"
                    for attachment_name, msg in errors.items()
                ]
            )
            if statements:
                self.env.cr.commit()  # save the correctly uploaded statements to the db before raising the errors
                raise RedirectWarning(
                    error_msg, result, _("View successfully imported statements")
                )
            else:
                raise UserError(error_msg)
        return result

    def _parse_bank_statement_file(self, attachment) -> tuple:
        """Override to add BBVA formats support"""
        if self._check_bbva_mx_attachment(attachment):
            file_content = base64.b64decode(attachment.datas)
            file_name = attachment.name.lower()
            if file_name.endswith(".txt"):
                result = self.env["bbva.parser"].parse_bbva_file(
                    file_content, self, file_type="txt"
                )
                return (None, None, [result])
            elif file_name.endswith((".xls", ".xlsx")):
                result = self.env["bbva.parser"].parse_bbva_file(
                    file_content, self, file_type="xlsx"
                )
                return (None, None, [result])
            else:
                raise UserError(
                    _(
                        f"File extension is not allowed for a {self.bank_id.name} Journal"
                    )
                )

        return super()._parse_bank_statement_file(attachment)

    def create_document_from_attachment(self, attachment_ids=None):
        journal = self or self.browse(self.env.context.get("default_journal_id"))
        if journal.type in ("bank", "credit", "cash") and journal._is_bbva_mx():
            attachments = self.env["ir.attachment"].browse(attachment_ids)
            if not attachments:
                raise UserError(_("No attachment was provided"))
            return journal._import_bbva_mx_bank_statement(attachments)
        return super().create_document_from_attachment(attachment_ids)

    @api.onchange("x_treatment")
    def _onchange_x_treatment(self):
        """Determine if the UUID is required based on the tax treatment of the journal."""
        for journal in self:
            journal.l10n_mx_edi_require_uuid = (
                journal.x_treatment in ["fiscal_simulated", "fiscal_real"]
                and journal.type == "purchase"
            )
