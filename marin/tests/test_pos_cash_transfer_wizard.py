from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.point_of_sale.tests.common import TestPoSCommon


@tagged("post_install", "-at_install", "cash_transfer_wizard")
class TestPOSCashTransferWizard(TestPoSCommon):
    @classmethod
    def setUpClass(cls, chart_template_ref="mx"):
        super().setUpClass(chart_template_ref=chart_template_ref)

    def setUp(self):
        super().setUp()
        self.config = self.basic_config
        self.session = self.open_new_session(2000)
        self.session.post_closing_cash_details(2000)
        self.session.close_session_from_ui()
        self.cash_2 = self.env["account.journal"].create({"name": "Test Cash", "code": "TCSH", "type": "cash"})
        self.user_partner = self.env["res.partner"].search([("user_ids", "=", self.env.user.id)], limit=1)

    def test_cash_transfer(self):
        """Testing case of creating a cash transfer
        Case 01: Open the cash transfer wizard
        Case 02: Create a cash transfer
        Case 03: Create a cash transfer with amount 0
        """
        # Case 01
        cash_transfer_wizard = self.session.open_pos_cash_transfer_wizard()
        self.assertEqual(cash_transfer_wizard["name"], "POS Cash Transfer")
        # Case 02
        currency_id = (
            self.env["account.journal"]
            .browse(cash_transfer_wizard["context"]["default_journal_id"])
            .company_id.currency_id.id
        )
        wizard = self.env["pos.cash.transfer.wizard"].create(
            {
                "pos_session_id": self.session.id,
                "amount": 100,
                "journal_id": cash_transfer_wizard["context"]["default_journal_id"],
                "destination_account_id": cash_transfer_wizard["context"]["default_destination_account_id"],
                "destination_journal_id": self.cash_2.id,
                "partner_id": self.user_partner.id,
                "currency_id": currency_id,
            }
        )
        cash_transfer_activity_id = wizard._get_activity_type_for_cash_transfer().id
        self.assertFalse(self.env["mail.activity"].search([("activity_type_id", "=", cash_transfer_activity_id)]))
        wizard.action_create_cash_transfer()
        self.assertTrue(self.env["mail.activity"].search([("activity_type_id", "=", cash_transfer_activity_id)]))
        # Case 03
        wizard = self.env["pos.cash.transfer.wizard"].create(
            {
                "pos_session_id": self.session.id,
                "amount": 0,
                "journal_id": cash_transfer_wizard["context"]["default_journal_id"],
                "destination_account_id": cash_transfer_wizard["context"]["default_destination_account_id"],
                "destination_journal_id": self.cash_2.id,
                "partner_id": self.user_partner.id,
                "currency_id": currency_id,
            }
        )
        with self.assertRaises(UserError):
            wizard.action_create_cash_transfer()

    def test_cash_transfer_without_activity(self):
        """Testing case of creating a cash transfer without activity type"""
        wizard = self.env["pos.cash.transfer.wizard"]
        wizard._get_activity_type_for_cash_transfer().unlink()
        cash_transfer_wizard = self.session.open_pos_cash_transfer_wizard()
        currency_id = (
            self.env["account.journal"]
            .browse(cash_transfer_wizard["context"]["default_journal_id"])
            .company_id.currency_id.id
        )
        transfer = wizard.create(
            {
                "pos_session_id": self.session.id,
                "amount": 100,
                "journal_id": cash_transfer_wizard["context"]["default_journal_id"],
                "destination_account_id": cash_transfer_wizard["context"]["default_destination_account_id"],
                "destination_journal_id": self.cash_2.id,
                "partner_id": self.user_partner.id,
                "currency_id": currency_id,
            }
        )
        transfer.action_create_cash_transfer()
