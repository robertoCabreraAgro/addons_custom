from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class PosSession(models.Model):
    """Inherit PosSession"""

    _inherit = "pos.session"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    # Extend field
    cash_register_balance_end_real = fields.Monetary(tracking=True)

    # New fields
    move_cash_transfer_ids = fields.One2many(
        comodel_name="account.move",
        inverse_name="pos_session_origin_id",
    )
    original_cash_register_balance_end_real = fields.Monetary(
        string="Original Ending Balance",
        currency_field="currency_id",
        compute="_compute_cash_transfer",
        store=True,
        readonly=True,
    )
    cash_transfered = fields.Monetary(
        string="Transfered",
        currency_field="currency_id",
        compute="_compute_cash_transfer",
        store=True,
        readonly=True,
        tracking=True,
    )
    count_liquidity_transfer_payment = fields.Integer(
        compute="_compute_count_liquidity_transfer_payment",
    )

    @api.depends(
        "move_cash_transfer_ids",
        "move_cash_transfer_ids.state",
        "move_cash_transfer_ids.journal_id",
    )
    def _compute_cash_transfer(self):
        for session in self:
            transfers = session.move_cash_transfer_ids.filtered(
                lambda m: m.state == "posted"
                and m.journal_id
                == session.config_id.payment_method_ids.journal_id.filtered(
                    lambda j: j.type == "cash"
                )[:1]
            )
            amount = sum(transfers.mapped("amount_total"))
            if amount != 0:
                session._confirmed_cash_transfer(amount)
            else:
                session.original_cash_register_balance_end_real = 0
                session.cash_transfered = 0

    # Cash Transfer smart button methods
    def _compute_count_liquidity_transfer_payment(self):
        for session in self:
            session.count_liquidity_transfer_payment = self.env[
                "account.move"
            ].search_count([("id", "in", self.move_cash_transfer_ids.ids)])

    def action_open_liquidity_transfers(self):
        self.ensure_one()
        action = {
            "name": _("Liquidity transfers"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "context": {"create": False},
            "view_mode": "list,form",
            "domain": [("id", "in", self.move_cash_transfer_ids.ids)],
        }
        return action

    def _confirmed_cash_transfer(self, cash_amount):
        self.ensure_one()
        if (
            not self.env.user.has_group("marin.group_pos_cash_transfer")
            and self.cash_transfered != cash_amount
        ):
            raise AccessError(
                _(
                    "You are not allowed to do Cash Transfers. Please contact an administrator."
                )
            )

        if not self.original_cash_register_balance_end_real:
            self.original_cash_register_balance_end_real = (
                self.cash_register_balance_end_real
            )
        self.cash_transfered = cash_amount
        self.cash_register_balance_end_real = (
            self.original_cash_register_balance_end_real - cash_amount
        )

    def _are_sufficient_funds(self, cash_amount):
        if not cash_amount <= self.cash_register_balance_end_real:
            raise UserError(
                _(
                    "Insufficient cash amount. Cash transfer is trying to use more cash than available on Pos Session."
                )
            )
