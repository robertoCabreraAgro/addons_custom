from odoo import _, fields, models
from odoo.exceptions import UserError


class PosConfig(models.Model):
    _inherit = "pos.config"

    active = fields.Boolean(default=True)

    def action_liquidity_transfer(self):
        self.ensure_one()
        if self.has_active_session:
            raise UserError(
                _("Liquidity transfer is only allowed when there is no active session.")
            )
        session = self.env["pos.session"].search(
            [
                ("config_id", "=", self.id),
                ("state", "=", "closed"),
                ("rescue", "=", False),
            ],
            order="id desc",
            limit=1,
        )
        cash_journal = self.payment_method_ids.journal_id.filtered(
            lambda j: j.type == "cash"
        )[:1]
        action = {
            "name": _("POS Cash Transfer"),
            "type": "ir.actions.act_window",
            "res_model": "pos.cash.transfer.wizard",
            "view_mode": "form",
            "view_id": self.env.ref("marin.wizard_pos_cash_transfer_form_view").id,
            "target": "new",
            "context": {
                "default_session_id": session.id,
                "default_journal_id": cash_journal.id,
                "default_currency_id": cash_journal.currency_id.id
                or cash_journal.company_id.currency_id.id,
                "default_amount": session.cash_register_balance_end_real,
            },
        }
        return action
