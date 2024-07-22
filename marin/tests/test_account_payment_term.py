from odoo.tests import tagged

from odoo.addons.account.tests.test_payment_term import TestAccountPaymentTerms


@tagged("post_install", "-at_install")
class TestPaymentTerm(TestAccountPaymentTerms):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_01_payment_term_immediate(self):
        """Ensure that field is_immediate is computed correctly"""
        self.assertTrue(self.pay_term_today.is_immediate)
        self.assertFalse(self.pay_term_net_30_days.is_immediate)
