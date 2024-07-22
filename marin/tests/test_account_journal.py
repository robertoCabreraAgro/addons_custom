from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestAccountJournal(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_01_journal_constraint(self):
        account = self.env["account.account"].search(
            [
                ("company_id", "=", self.env.company.id),
                ("account_type", "=", "asset_fixed"),
            ],
            limit=1,
        )
        with self.assertRaises(UserError):
            self.env["account.journal"].create(
                {
                    "code": "NEW",
                    "name": "Type Test",
                    "type": "sale",
                    "default_receivable_account_id": account.id,
                }
            )
