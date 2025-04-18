import re
from itertools import product
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.addons.base.models.res_bank import sanitize_account_number


class AccountBankStatementLine(models.Model):
    """Inherit AccountBankStatementLine"""

    _inherit = "account.bank.statement.line"

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for absl in res.filtered(lambda x: not x.partner_id):
            partner = absl._retrieve_partner()
            if partner:
                absl.partner_id = partner
        return res

    def _compute_st_lines_to_reconcile(self, configured_company, batch_size=None,):
        # Find the bank statement lines that are not reconciled and try to reconcile them automatically.
        # The ones that are never be processed by the CRON before are processed first.
        remaining_line_id = None
        limit = batch_size + 1 if batch_size else None
        start_time = fields.Datetime.now()
        domain = [
            ('is_reconciled', '=', False),
            ('create_date', '>', start_time.date() - relativedelta(months=3)),
            ('company_id', 'in', configured_company.ids),
        ]
        st_lines = self.search(domain, limit=limit, order="cron_last_check ASC NULLS FIRST, id")
        if batch_size and len(st_lines) > batch_size:
            remaining_line_id = st_lines[batch_size].id
            st_lines = st_lines[:batch_size]
        return st_lines, remaining_line_id

    # Override original method
    def _retrieve_partner(self):
        self.ensure_one()

        # Retrieve the partner from the statement line.
        if self.partner_id:
            return self.partner_id

        # Retrieve the partner from the bank account.
        if self.account_number:
            account_number_nums = sanitize_account_number(self.account_number)
            if account_number_nums:
                domain = [("sanitized_acc_number", "ilike", account_number_nums)]
                for extra_domain in (
                    [("company_id", "parent_of", self.company_id.id)],
                    [("company_id", "=", False)],
                ):
                    bank_accounts = self.env["res.partner.bank"].search(
                        extra_domain + domain
                    )
                    if len(bank_accounts.partner_id) == 1:
                        return bank_accounts.partner_id

                    else:
                        # We have several partner with same account, possibly some archived partner
                        # so try to filter out inactive partner and if one remains, select this one
                        bank_accounts = bank_accounts.filtered(
                            lambda bacc: bacc.partner_id.active
                        )
                        if len(bank_accounts) == 1:
                            return bank_accounts.partner_id

        if self.payment_ref:
            vals = re.split(r" |/|,|:", self.payment_ref)
            for item in vals:
                if not (len(item) == 10 or len(item) == 16):
                    continue

                bank_accounts = self.env["res.partner.bank"].search(
                    [("acc_number", "=", item)], limit=1
                )
                if bank_accounts and bank_accounts.partner_id:
                    return bank_accounts.partner_id.id

        # Retrieve the partner from the partner name.
        if self.partner_name:
            # using 'complete_name' instead of 'name',
            # as 'complete_name' is the first search criteria in _rec_names_search,
            # and trigram indexed accordingly.
            domains = product(
                [
                    ("complete_name", "=ilike", self.partner_name),
                    ("complete_name", "ilike", self.partner_name),
                ],
                [
                    ("company_id", "parent_of", self.company_id.id),
                    ("company_id", "=", False),
                ],
            )
            for domain in domains:
                partner = self.env["res.partner"].search(
                    list(domain) + [("parent_id", "=", False)], limit=2
                )
                if len(partner) == 1:
                    return partner

        # Retrieve the partner from the 'reconcile models'.
        rec_models = self.env["account.reconcile.model"].search(
            [
                *self.env["account.reconcile.model"]._check_company_domain(self.company_id),
                ("rule_type", "!=", "writeoff_button"),
            ]
        )
        for rec_model in rec_models:
            partner = rec_model._get_partner_from_mapping(self)
            if partner and rec_model._is_applicable_for(self, partner):
                return partner

        return self.env["res.partner"]
