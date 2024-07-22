from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class PosSession(models.Model):
    _inherit = "pos.session"

    cash_original_ending_balance = fields.Monetary(
        string="Original Ending Balance",
        readonly=True,
        currency_field="currency_id",
        store=True,
        compute="_compute_cash_transfer",
    )
    cash_transfered = fields.Monetary(
        string="Transfered",
        readonly=True,
        tracking=True,
        currency_field="currency_id",
        store=True,
        compute="_compute_cash_transfer",
    )
    cash_register_balance_end_real = fields.Monetary(tracking=True)
    cash_transfer_payment_ids = fields.One2many("account.payment", "cash_transfer_pos_id")
    cash_transfer_payment_count = fields.Integer(compute="_compute_cash_transfer_payment_count")

    @api.depends(
        "cash_transfer_payment_ids", "cash_transfer_payment_ids.state", "cash_transfer_payment_ids.payment_type"
    )
    def _compute_cash_transfer(self):
        payments = self.cash_transfer_payment_ids.filtered(
            lambda payment: payment.state == "posted" and payment.payment_type == "outbound"
        )
        amount = sum(payments.mapped("amount"))
        if amount != 0:
            self._confirmed_cash_transfer(amount)
        else:
            self.cash_original_ending_balance = 0
            self.cash_transfered = 0

    def open_pos_cash_transfer_wizard(self):
        self.ensure_one()
        self._is_last_closed_session()
        cash_journal = self.config_id.payment_method_ids.journal_id.filtered(lambda j: j.type == "cash")[:1]

        if not cash_journal:
            raise UserError(
                _("The used POS has no CASH Payment method or journal correctly configured, please check for them.")
            )

        action = {
            "name": "POS Cash Transfer",
            "view_mode": "form",
            "res_model": "pos.cash.transfer.wizard",
            "type": "ir.actions.act_window",
            "view_id": self.env.ref("marin.wizard_pos_cash_transfer_form_view").id,
            "target": "new",
            "context": {
                "default_amount": self.cash_register_balance_end_real,
                "default_journal_id": cash_journal.id,
                "default_destination_account_id": cash_journal.company_id.transfer_account_id.id,
                "default_destination_journal_id": self.company_id.pos_cash_transfer_journal_id.id,
                "default_pos_session_id": self.id,
                "default_partner_id": self.company_id.partner_id.id,
            },
        }

        return action

    def _confirmed_cash_transfer(self, cash_amount):
        self.ensure_one()
        if self.cash_transfered != cash_amount:
            if not self.env.user.has_group("marin.group_pos_cash_transfer"):
                raise AccessError(_("Permission needed"))
        if self.cash_original_ending_balance == 0:
            self.cash_original_ending_balance = self.cash_register_balance_end_real
        self.cash_transfered = cash_amount
        self.cash_register_balance_end_real = self.cash_original_ending_balance - cash_amount

    # Pos Sessions constraints
    def _is_last_closed_session(self):
        last_pos_session = self.config_id.session_ids[:1]
        if self != last_pos_session or self.config_id.has_active_session:
            raise UserError(_("Cash transfer is only allowed for the last closed POs Session."))

    def _cash_transfer_sufficient_funds(self, cash_amount):
        if not cash_amount <= self.cash_register_balance_end_real:
            raise UserError(
                _("Insufficient cash amount. Cash transfer is trying to use more cash than available on Pos Session.")
            )

    # Cash Transfer smart button methods
    def _compute_cash_transfer_payment_count(self):
        for record in self:
            record.cash_transfer_payment_count = self.env["account.payment"].search_count(
                [("id", "in", self.cash_transfer_payment_ids.ids)]
            )

    def get_cash_transfer_payments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Cash Transfer Payments",
            "view_mode": "tree,form",
            "res_model": "account.payment",
            "domain": [("id", "in", self.cash_transfer_payment_ids.ids)],
        }

    def _get_pos_ui_res_users(self, params):
        user = self.env["res.users"].search_read(**params["search_params"])[0]
        user["role"] = (
            "manager" if any(id == self.config_id.group_pos_manager_id.id for id in user["groups_id"]) else "cashier"
        )
        user["cost_access"] = any(
            id == self.env.ref("marin.group_product_cost_readonly").id for id in user["groups_id"]
        )
        del user["groups_id"]
        return user
