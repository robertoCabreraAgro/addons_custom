from datetime import datetime, timedelta

from odoo import Command
from odoo.tests import tagged

from odoo.addons.l10n_mx_edi.tests.common import TestMxEdiCommon


@tagged("post_install", "-at_install")
class TestL10nMxTaxCashBasis(TestMxEdiCommon):
    def setUp(self):
        super().setUp()
        self.account_move_model = self.env["account.move"]
        self.account_model = self.env["account.account"]
        self.register_payments_model = self.env["account.payment.register"]
        tz = self.env["l10n_mx_edi.certificate"].sudo()._get_timezone()
        self.today = datetime.now(tz)
        self.mxn = self.env.ref("base.MXN")
        self.usd = self.env.ref("base.USD")
        self.usd.active = True
        self.invoice = self._create_invoice()
        company = self.invoice.company_id
        company.write({"currency_id": self.mxn.id})
        self.tax_cash_basis_journal_id = company.tax_cash_basis_journal_id
        self.curr_ex_journal_id = company.currency_exchange_journal_id
        self.account_type = "liability_current"
        self.payment_method_manual_out = self.env.ref("account.account_payment_method_manual_out")
        self.payment_method_manual_in = self.env.ref("account.account_payment_method_manual_in")
        self.bank_journal_mxn = self.env["account.journal"].create(
            {
                "name": "Bank MXN",
                "type": "bank",
                "code": "BNK37",
            }
        )
        self.journal = self.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", self.invoice.company_id.id)], limit=1
        )
        self.iva_tag = self.env["account.account.tag"].search([("name", "=", "IVA")])
        self.tax_account = self.create_account("11111101", "Tax Account")
        cash_tax_account = self.create_account("77777777", "Cash Tax Account")
        account_tax_cash_basis = self.create_account("99999999", "Tax Base Account")
        self.tax_16 = self.env["account.chart.template"].ref("tax14")
        self.tax_16.write(
            {
                "cash_basis_transition_account_id": cash_tax_account.id,
            }
        )
        self.tax_16.company_id.write(
            {
                "account_cash_basis_base_account_id": account_tax_cash_basis.id,
            }
        )
        self.tax_16.invoice_repartition_line_ids.write({"account_id": self.tax_account.id})
        self.tax_16.refund_repartition_line_ids.write({"account_id": self.tax_account.id})
        self.product.supplier_taxes_id = [self.tax_16.id]

        self.set_currency_rates(mxn_rate=21, usd_rate=1)

    def create_payment(self, invoice, date, journal, currency):
        statement_line = self.env["account.bank.statement.line"].create(
            {
                "journal_id": journal.id,
                "payment_ref": "mx_st_line",
                "partner_id": invoice.partner_id.id,
                "amount": -invoice.amount_total,
            }
        )
        _dummy, st_suspense_lines, _st_other_lines = statement_line.with_context(
            skip_account_move_synchronization=True
        )._seek_for_lines()
        receivable_line = invoice.line_ids.filtered(lambda line: line.account_type == "liability_payable")
        st_suspense_lines.account_id = receivable_line.account_id

        (receivable_line + st_suspense_lines).reconcile()
        return statement_line.move_id

    def delete_journal_data(self):
        """Delete journal data
        delete all journal-related data, so a new currency can be set.
        """

        # 1. Reset to draft moves (invoices), so some records may be deleted
        company = self.invoice.company_id
        moves = self.env["account.move"].search([("company_id", "=", company.id)])
        moves = moves - moves.filtered(lambda m: m.state == "draft")
        moves.button_draft()
        # 2. Delete related records
        models_to_clear = ["account.move.line", "account.payment", "account.bank.statement"]
        for model in models_to_clear:
            records = self.env[model].search([("company_id", "=", company.id)])
            records.with_context(dynamic_unlink=True).unlink()

    def create_account(self, code, name, account_type=False):
        """This account is created to use like cash basis account and only
        it will be filled when there is payment
        """
        return self.account_model.create(
            {
                "name": name,
                "code": code,
                "account_type": account_type or self.account_type,
            }
        )

    def test_instead_of_reverting_entry_delete_it(self):
        """What I expect from here:
        - On Payment unreconciliation cash flow journal entry is deleted
        """
        self.delete_journal_data()
        self.tax_account.write({"reconcile": True})
        self.env["res.config.settings"].write({"group_multi_currency": True})
        cash_am_ids = self.env["account.move"].search([("journal_id", "in", self.tax_cash_basis_journal_id.ids)])
        self.assertFalse(cash_am_ids, "There should be no journal entry")

        invoice_date = self.today - timedelta(days=1)
        invoice_id = self.invoice.copy(
            {
                "move_type": "in_invoice",
                "currency_id": self.usd.id,
                "date": invoice_date.date(),
                "invoice_date": invoice_date.date(),
                "journal_id": self.journal.id,
            }
        )
        invoice_id.invoice_line_ids = [
            Command.create(
                {
                    "account_id": self.product.product_tmpl_id.get_product_accounts()["income"].id,
                    "product_id": self.product.id,
                    "quantity": 1,
                    "price_unit": 450,
                    "product_uom_id": self.product.uom_id.id,
                    "name": self.product.name,
                    "tax_ids": [Command.set(self.tax_16.ids)],
                },
            )
        ]
        invoice_id.action_post()
        self.create_payment(invoice_id, self.today, self.bank_journal_mxn, self.usd)
        cash_am_ids = self.env["account.move"].search([("journal_id", "in", self.tax_cash_basis_journal_id.ids)])
        self.assertEqual(len(cash_am_ids), 1, "There should be one journal entry")
        invoice_id.line_ids.sudo().remove_move_reconcile()

        cash_am_ids = self.env["account.move"].search([("journal_id", "in", self.tax_cash_basis_journal_id.ids)])
        self.assertFalse(cash_am_ids, "There should be no journal entry")

    def test_reverting_exchange_difference_from_non_mxn(self):
        self.delete_journal_data()
        country_id = self.env.ref("base.us").id
        self.invoice.company_id.write(
            {
                "country_id": country_id,
                "account_fiscal_country_id": country_id,
            }
        )

        tax_group_us = self.tax_16.tax_group_id.copy({"country_id": country_id})
        self.tax_16.country_id = country_id
        self.tax_16.tax_group_id = tax_group_us
        cash_am_ids = self.env["account.move"].search([("journal_id", "in", self.curr_ex_journal_id.ids)])
        self.assertFalse(cash_am_ids, "There should be no journal entry")

        invoice_date = self.today - timedelta(days=1)
        invoice_id = self.invoice.copy(
            {
                "move_type": "in_invoice",
                "currency_id": self.usd.id,
                "date": invoice_date.date(),
                "invoice_date": invoice_date.date(),
                "journal_id": self.journal.id,
            }
        )

        invoice_id.invoice_line_ids = [
            Command.create(
                {
                    "account_id": self.product.product_tmpl_id.get_product_accounts()["income"].id,
                    "product_id": self.product.id,
                    "quantity": 1,
                    "price_unit": 450,
                    "product_uom_id": self.product.uom_id.id,
                    "name": self.product.name,
                    "tax_ids": [Command.set(self.tax_16.ids)],
                },
            )
        ]
        invoice_id.action_post()

        self.create_payment(invoice_id, self.today, self.bank_journal_mxn, self.mxn)
        cash_am_ids = self.env["account.move"].search([("journal_id", "in", self.curr_ex_journal_id.ids)])
        self.assertEqual(len(cash_am_ids), 1, "There should be One journal entry")

        invoice_id.line_ids.sudo().remove_move_reconcile()
        cash_am_ids = self.env["account.move"].search([("journal_id", "in", self.curr_ex_journal_id.ids)])
        self.assertEqual(len(cash_am_ids), 2, "There should be two journal entry")

    def set_currency_rates(self, mxn_rate, usd_rate):
        date = self.today.date()
        self.mxn.rate_ids.filtered(lambda r: r.name == date).unlink()
        self.mxn.rate_ids = self.env["res.currency.rate"].create(
            {"rate": mxn_rate, "name": date, "currency_id": self.mxn.id}
        )
        self.usd.rate_ids.filtered(lambda r: r.name == date).unlink()
        self.usd.rate_ids = self.env["res.currency.rate"].create(
            {"rate": usd_rate, "name": date, "currency_id": self.usd.id}
        )
