from odoo import api, fields, models


class AccountAccount(models.Model):
    """Inherit AccountAccount"""

    _inherit = "account.account"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    x_code = fields.Char(
        compute="_compute_x_code",
        store=True,
        readonly=False,
        help="Field introduced to keep custom order when reordering accounts at migration",
    )

    # ------------------------------------------------------------
    # COMPUTHE METHODS
    # ------------------------------------------------------------

    @api.depends("code_store")
    def _compute_x_code(self):
        """Compute x_code based on code_store consistency across companies.

        If all companies using this account have the same code_store value,
        store that code. Otherwise, store "uncodable" to indicate inconsistency.
        """
        for account in self:
            # Get all companies that use this account
            company_ids = account.company_ids.ids
            if not company_ids:
                account.x_code = account.code_store or ""
                continue

            # Check code_store value for each company
            codes = set()
            for company in account.company_ids:
                code_value = account.with_company(company).code_store
                codes.add(code_value or "")

            # If all companies have the same code, use it; otherwise mark as "uncodable"
            if len(codes) == 1:
                account.x_code = codes.pop()
            else:
                account.x_code = "uncodable"
