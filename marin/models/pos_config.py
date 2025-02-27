from odoo import _, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"


    active = fields.Boolean(default=True)


    def open_pos_cash_transfer_wizard(self):
        session = self.session_ids[:1]
        payment = session.cash_transfer_payment_ids.filtered(lambda pay: pay.state == "draft")[:1]
        if payment:
            return {
                "name": _("Payments"),
                "type": "ir.actions.act_window",
                "res_model": "account.payment",
                "context": {"create": False},
                "view_mode": "form",
                "res_id": payment.id,
            }
        return session.open_pos_cash_transfer_wizard()
