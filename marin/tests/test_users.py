from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.mail.tests.common import mail_new_test_user


@tagged("users", "post_install", "-at_install")
class TestUsers(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.user.company_id
        cls.user = mail_new_test_user(
            cls.env,
            login="user_test",
            name="User Test",
            email="user_test@test.example.com",
            company_id=cls.company.id,
            groups="sales_team.group_sale_salesman",
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Partner Test",
            }
        )
        cls.sale_journal = cls.env["account.journal"].create(
            {
                "company_id": cls.company.id,
                "type": "sale",
                "code": "SALE",
                "name": "SALE",
            }
        )

    def test_01_default_sale_journal(self):
        default_journal = self.env["account.journal"].search(
            [("company_id", "=", self.env.company.id), ("type", "=", "sale")], limit=1
        )
        self.assertTrue(default_journal != self.sale_journal)
        self.user.property_sale_journal_id = False
        journal = self.user._get_default_sale_journal_id()
        self.assertEqual(journal, default_journal)
        self.user.property_sale_journal_id = self.sale_journal
        journal = self.user._get_default_sale_journal_id()
        self.assertEqual(journal, self.sale_journal)

    def test_02_user_groups(self):
        partner = self.partner.with_user(self.user)
        partner._compute_group()
        self.assertRecordValues(
            self.partner,
            [
                {
                    "user_account_user": False,
                    "user_account_manager": False,
                    "user_purchase_user": False,
                    "user_purchase_manager": False,
                    "user_sale_user": False,
                    "user_sale_manager": False,
                    "user_stock_user": False,
                    "user_stock_manager": False,
                    "user_debt_manager": False,
                }
            ],
        )
        self.user.groups_id |= (
            self.env.ref("marin.group_account_manager")
            | self.env.ref("marin.group_purchase_user")
            | self.env.ref("marin.group_sale_manager")
            | self.env.ref("marin.group_account_debt_manager")
        )
        partner._compute_group()
        self.assertRecordValues(
            self.partner,
            [
                {
                    "user_account_user": True,
                    "user_account_manager": True,
                    "user_purchase_user": True,
                    "user_purchase_manager": False,
                    "user_sale_user": True,
                    "user_sale_manager": True,
                    "user_stock_user": False,
                    "user_stock_manager": False,
                    "user_debt_manager": True,
                }
            ],
        )
