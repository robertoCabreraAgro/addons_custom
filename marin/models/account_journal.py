from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountJournalInherit(models.Model):
    _inherit = "account.journal"

    default_receivable_account_id = fields.Many2one(
        "account.account",
        "Default Receivable Account",
        check_company=True,
        domain=[
            ("deprecated", "=", False),
            ("account_type", "=", "asset_receivable")
        ],
        copy=False,
        ondelete="restrict",
        help="It acts as a default account for receivable amount instead of the Company's default",
    )
    default_payable_account_id = fields.Many2one(
        "account.account",
        "Default Payable Account",
        check_company=True,
        domain=[
            ("deprecated", "=", False),
            ("account_type", "=", "liability_payable")
        ],
        copy=False,
        ondelete="restrict",
        help="It acts as a default account for payable amount instead of the Company's default",
    )
    default_refund_account_id = fields.Many2one(
        "account.account",
        "Default Refund Account",
        check_company=True,
        domain=[
            ("deprecated", "=", False),
            ("account_type", "in", ("expense", "expense_direct_cost", "income", "income_other"))
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
        "Treatment",
        default="not_fiscal_real",
        help="Technical field used to group journal and journal moves according to fiscal logic.",
    )
    can_access_user_ids = fields.Many2many(
        "res.users",
        "account_journal_res_users_access_rel",
        "journal_id",
        "user_id",
        "Allowed Users",
        help="Users that can visualize and perform actions on this journal.",
    )

    @api.constrains("type", "default_receivable_account_id", "default_payable_account_id")
    def _check_type_default_receivable_payable_account_id_type(self):
        journals_to_check = self.filtered(lambda journal: journal.type in ("sale", "purchase"))
        accounts_to_check = journals_to_check.mapped("default_receivable_account_id") + journals_to_check.mapped(
            "default_payable_account_id"
        )
        if any(account.account_type not in ("asset_receivable", "liability_payable") for account in accounts_to_check):
            raise UserError(
                _("The type of the journal's default receivable/payable account should be 'receivable' or 'payable'.")
            )
