
from odoo import _, api, fields, models, Command
from odoo.exceptions import UserError



class PosCashTransferWizard(models.TransientModel):
    _name = "pos.cash.transfer.wizard"
    _description = "PoS Cash Transfer Wizard"


    session_id = fields.Many2one(
        comodel_name="pos.session",
        required=True,
        readonly=True,
    )
    journal_id = fields.Many2one(
        comodel_name="account.journal",
        required=True,
        readonly=True,
        domain=[("type", "in", ["cash", "bank"])],
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        required=True,
        readonly=True,
        help="The payment's currency.",
    )
    destination_journal_id = fields.Many2one(
        comodel_name="account.journal",
        required=True,
        domain=[("type", "in", ["cash", "bank"])],
    )
    amount = fields.Monetary(
        currency_field="currency_id",
        required=True,
    )


    @api.onchange("journal_id")
    def _onchange_currency_id(self):
        self.ensure_one()
        self.currency_id = self.journal_id.currency_id or self.journal_id.company_id.currency_id

    def _prepare_move_origin(self):
        line_vals = [
            {
                'name': _('Liquidity transfer'),
                'account_id': self.env.company.transfer_account_id.id,
                'debit': self.amount,
                'credit': 0.0,
            },
            {
                'name': _('Liquidity transfer'),
                'account_id': self.journal_id.default_account_id.id,
                'debit': 0.0,
                'credit': self.amount,
            },
        ]
        vals = {
            "company_id": self.env.company.id,
            "journal_id": self.journal_id.id,
            "move_type": "entry",
            "date": fields.Date.today(),
            "line_ids": [
                Command.create(vals) for vals in line_vals
            ],
            "pos_session_origin_id": self.session_id.id,
        }
        return vals

    def _prepare_move_destination(self):
        line_vals = [
            {
                'name': _('Liquidity transfer'),
                'account_id': self.env.company.transfer_account_id.id,
                'debit': 0.0,
                'credit': self.amount,
            },
            {
                'name': _('Liquidity transfer'),
                'account_id': self.destination_journal_id.default_account_id.id,
                'debit': self.amount,
                'credit': 0.0,
            },
        ]
        vals = {
            "company_id": self.env.company.id,
            "journal_id": self.destination_journal_id.id,
            "move_type": "entry",
            "date": fields.Date.today(),
            "line_ids": [
                Command.create(vals) for vals in line_vals
            ],
            "pos_session_origin_id": self.session_id.id,
        }
        return vals

    def _create_cash_transfers(self):
        origin = self.env["account.move"].create(self._prepare_move_origin())
        origin.action_post()
        destination = self.env["account.move"].create(self._prepare_move_destination())
        destination.action_post()
        return origin | destination

    def action_create_cash_transfer(self):
        if self.amount == 0.0:
            raise UserError(_("Please specify an amount for the cash transfer different of 0.0"))
        self.session_id._are_sufficient_funds(self.amount)
        moves = self._create_cash_transfers()
        action = {
            "name": _("Liquidity transfers"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "context": {"create": False},
            "view_mode": "list,form",
            'domain': [('id', 'in', moves.ids)],
        }
        return action
