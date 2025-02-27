from odoo import _, api, fields, models


class AccountPayment(models.Model):
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
                pay.destination_account_id = (
                    accounts.get("customer")
                    or self.env["account.account"].with_company(pay.company_id).search(
                        [
                            *self.env["account.account"]._check_company_domain(pay.company_id),
                            ("deprecated", "=", False),
                            ("account_type", "=", "asset_receivable"),
                        ],
                        limit=1
                    )
                )
            elif pay.partner_type == "supplier":
                pay.destination_account_id = (
                    accounts.get("supplier")
                    or self.env["account.account"].with_company(pay.company_id).search(
                        [
                            *self.env["account.account"]._check_company_domain(pay.company_id),
                            ("deprecated", "=", False),
                            ("account_type", "=", "liability_payable"),
                        ],
                        limit=1
                    )
                )

    def _get_destination_accounts(self):
        return {
            "customer": 
                self.partner_id.with_company(self.company_id).property_account_receivable_id
                or self.journal_id.default_receivable_account_id,
            "supplier":
                self.partner_id.with_company(self.company_id).property_account_payable_id
                or self.journal_id.default_payable_account_id,
        }
