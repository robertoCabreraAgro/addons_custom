import re

from odoo import api, models


class AccountBankStatementLineInherit(models.Model):
    _inherit = "account.bank.statement.line"

    def _predict_partner_from_payment_ref(self):
        partner_bank = self.env["res.partner.bank"]
        vals = re.split(r" |/|,|:", self.payment_ref)
        for item in vals:
            if not (len(item) == 10 or len(item) == 16):
                continue
            bank = partner_bank.search([("acc_number", "=", item)], limit=1)
            if bank and bank.partner_id:
                self.partner_id = bank.partner_id
                break

    @api.onchange("payment_ref")
    def _onchange_payment_ref(self):
        for absl in self:
            if absl.payment_ref:
                absl._predict_partner_from_payment_ref()
