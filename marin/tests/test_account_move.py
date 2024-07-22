from odoo.exceptions import UserError
from odoo.tests import Form, tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestInvoicing(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.invoice = cls.init_invoice("out_invoice", products=cls.product_a)
        cls.vendor_bill = cls.init_invoice("in_invoice", products=cls.product_a)
        cls.pay_term_net_30_days = cls.env["account.payment.term"].create(
            {
                "name": "Net 30 days",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "value_amount": 100,
                            "value": "percent",
                            "nb_days": 30,
                        },
                    ),
                ],
            }
        )

    def test_01_invoice_authorize_debt(self):
        invoice = self.invoice
        invoice.invoice_payment_term_id = self.pay_term_net_30_days
        partner = invoice.commercial_partner_id
        invoice.company_id.account_use_credit_limit = True
        partner.credit_limit = 1
        invoice.invoice_line_ids.price_unit = 10.0
        invoice._compute_partner_credit_warning()
        partner.credit_on_hold = True
        self.env.user.groups_id = [(3, self.env.ref("marin.group_account_debt_manager").id)]
        with self.assertRaises(UserError):
            invoice.action_post()
        partner.credit_on_hold = False
        with self.assertRaises(UserError):
            invoice.action_post()
        self.env.user.groups_id = [(4, self.env.ref("marin.group_account_debt_manager").id)]
        res = invoice.action_post()
        self.assertEqual(invoice.state, "draft")
        self.assertEqual(res.get("res_model"), "authorize.debt.wizard")
        wizard = self.env["authorize.debt.wizard"].with_context(**res.get("context")).create([{}])
        wizard._compute_from_record_ids()
        self.assertEqual(wizard.flag, "credit")
        self.assertEqual(wizard.count_so, 0)
        self.assertEqual(wizard.count_move, 1)
        wizard.action_move_increase_debt_limit_and_post()
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(partner.credit_limit, 11.5)

    def test_02_invoice_authorize_debt_multi(self):
        self.env.user.groups_id = [(4, self.env.ref("marin.group_account_debt_manager").id)]
        invoice = self.invoice
        invoice.invoice_payment_term_id = self.pay_term_net_30_days
        partner = invoice.commercial_partner_id
        invoice.company_id.account_use_credit_limit = True
        partner.credit_limit = 10
        invoice.invoice_line_ids.price_unit = 10.0
        invoice._compute_partner_credit_warning()
        invoice2 = invoice.copy()
        res = invoice.action_post()
        self.assertEqual(invoice.state, "draft")
        self.assertEqual(res.get("res_model"), "authorize.debt.wizard")
        res["context"]["active_ids"] = (invoice | invoice2).ids
        wizard = self.env["authorize.debt.wizard"].with_context(**res["context"]).create([{}])
        wizard._compute_from_record_ids()
        self.assertEqual(wizard.flag, "credit")
        self.assertEqual(wizard.count_so, 0)
        self.assertEqual(wizard.count_move, 2)
        wizard.action_move_increase_debt_limit_and_post()
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(invoice2.state, "posted")
        self.assertEqual(partner.credit_limit, 23)

    def test_03_invoice_authorize_errors(self):
        self.env.user.groups_id = [(4, self.env.ref("marin.group_account_debt_manager").id)]
        ctx = {"active_model": "account.move", "active_ids": []}
        with self.assertRaisesRegex(
            UserError, "You can't authorize debt because the records dont match the criteria."
        ):
            self.env["authorize.debt.wizard"].with_context(**ctx).create([{}])
        invoice = self.invoice
        invoice2 = invoice.copy({"partner_id": invoice.partner_id.copy().id})
        ctx["active_ids"] = (invoice | invoice2).ids
        with self.assertRaisesRegex(UserError, "You cant authorize debt for records belonging to different partners."):
            self.env["authorize.debt.wizard"].with_context(**ctx).create([{}])
        invoice.invoice_line_ids.price_unit = 0.0
        ctx["active_ids"] = invoice.ids
        with self.assertRaisesRegex(
            UserError, "You can't authorize debt because the records dont match the criteria."
        ):
            self.env["authorize.debt.wizard"].with_context(**ctx).create([{}])
        invoice.invoice_line_ids.price_unit = 10.0
        vendor_bill = self.vendor_bill
        ctx["active_ids"] = (invoice | vendor_bill).ids
        with self.assertRaisesRegex(
            UserError, "You can't authorize debt for records being either all inbound, either all outbound."
        ):
            self.env["authorize.debt.wizard"].with_context(**ctx).create([{}])

    # def test_04_vendor_bill_authorize_debt(self):
    #     vendor_bill = self.vendor_bill
    #     vendor_bill.invoice_payment_term_id = self.pay_term_net_30_days
    #     partner = vendor_bill.commercial_partner_id
    #     vendor_bill.company_id.account_use_credit_limit = True
    #     partner.debit_limit = 1
    #     vendor_bill.invoice_line_ids.price_unit = 10.0
    #     vendor_bill._compute_partner_credit_warning()
    #     partner.debit_on_hold = True
    #     with self.assertRaises(UserError):
    #         vendor_bill.action_post()
    #     partner.debit_on_hold = False
    #     with self.assertRaises(UserError):
    #         vendor_bill.action_post()
    #     self.env.user.groups_id = [(4, self.env.ref("marin.group_account_debt_manager").id)]
    #     res = vendor_bill.action_post()
    #     self.assertEqual(vendor_bill.state, "draft")
    #     self.assertEqual(res.get("res_model"), "authorize.debt.wizard")
    #     wizard = self.env["authorize.debt.wizard"].with_context(**res.get("context")).create([{}])
    #     wizard._compute_from_record_ids()
    #     self.assertEqual(wizard.flag, "debit")
    #     self.assertEqual(wizard.count_so, 0)
    #     self.assertEqual(wizard.count_move, 1)
    #     wizard.action_move_increase_debt_limit_and_post()
    #     self.assertEqual(vendor_bill.state, "posted")
    #     self.assertEqual(partner.debit_limit, 11.5)

    def test_05_invoice_price_history(self):
        invoice = self.invoice
        invoice2 = invoice.copy()
        invoice3 = invoice.copy()
        invoice4 = invoice.copy()
        invoice.invoice_line_ids.price_unit = 5.0
        invoice.action_post()
        invoice2.invoice_line_ids.price_unit = 7.50
        invoice2.action_post()
        invoice3.invoice_line_ids.price_unit = 10.00
        with Form(self.env["invoice.line.price.history"]) as form_wiz:
            form_wiz.product_id = invoice.invoice_line_ids.product_id
            form_wiz.partner_id = invoice.partner_id
        wiz = form_wiz.save()
        wiz.line_id = invoice4.invoice_line_ids[0]
        wiz._onchange_partner_id()
        self.assertRecordValues(
            wiz.line_ids,
            [
                {
                    "line_id": invoice2.invoice_line_ids.id,
                    "price_unit": 7.5,
                },
                {
                    "line_id": invoice.invoice_line_ids.id,
                    "price_unit": 5.0,
                },
            ],
        )
        with Form(wiz) as form_wiz:
            form_wiz.include_draft = True
        wiz = form_wiz.save()
        wiz._onchange_partner_id()
        self.assertRecordValues(
            wiz.line_ids,
            [
                {
                    "line_id": invoice3.invoice_line_ids.id,
                    "price_unit": 10.0,
                },
                {
                    "line_id": invoice2.invoice_line_ids.id,
                    "price_unit": 7.5,
                },
                {
                    "line_id": invoice.invoice_line_ids.id,
                    "price_unit": 5.0,
                },
            ],
        )

    def test_06_invoice_cash_discount(self):
        invoice = self.invoice
        invoice.invoice_line_ids.price_unit = 10.00
        invoice.invoice_line_ids.quantity = 100.00
        action = invoice.action_cash_discount_wizard()
        self.env.user.groups_id = [(4, self.env.ref("marin.group_account_move_cash_discount").id)]
        with self.assertRaisesRegex(UserError, "You can only register cash discounts on posted moves."):
            self.env["account.invoice.cash.discount"].with_context(action.get("context", {})).create({})
        invoice.action_post()
        wiz = self.env["account.invoice.cash.discount"].with_context(action.get("context", {})).create({})
        wiz.amount = 15
        wiz.action_invoice_cash_discount()
        self.assertEqual(invoice.invoice_line_ids.price_unit, 8.5)
        self.assertEqual(invoice.invoice_line_ids.quantity, 100)
        self.assertEqual(invoice.invoice_line_ids.price_subtotal, 850.0)
