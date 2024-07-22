import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PosCashTransferWizard(models.TransientModel):
    _name = "pos.cash.transfer.wizard"
    _description = "PoS Cash Transfer Wizard"

    amount = fields.Monetary(
        currency_field="currency_id",
        required=True,
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        readonly=True,
        help="The payment's currency.",
        required=True,
    )
    journal_id = fields.Many2one(
        "account.journal",
        required=True,
        readonly=True,
    )
    destination_journal_id = fields.Many2one(
        "account.journal",
        required=True,
        domain=[("type", "in", ["cash", "bank"])],
    )
    destination_account_id = fields.Many2one(
        "account.account",
        readonly=True,
        required=True,
    )
    pos_session_id = fields.Many2one(
        "pos.session",
        readonly=True,
        required=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        readonly=True,
        required=True,
    )

    @api.model
    def default_get(self, list_fields):
        res = super().default_get(list_fields)
        journal = self.env["account.journal"].browse(self._context.get("default_journal_id"))
        res.update(
            {
                "currency_id": journal.currency_id.id or journal.company_id.currency_id.id,
            }
        )
        return res

    def _get_activity_type_for_cash_transfer(self):
        return self.env.ref("marin.cash_transfer_activity", raise_if_not_found=False)

    def _create_cash_transfer_payment(self):
        if self.amount == 0.0:
            raise UserError(_("Please specify an amount for the cash transfer different of 0.0"))
        default_values = {
            "payment_type": "outbound",
            "partner_type": "supplier",
            "partner_id": self.partner_id.id,
            "amount": self.amount,
            "journal_id": self.journal_id.id,
            "is_internal_transfer": True,
            "destination_journal_id": self.destination_journal_id.id,
            "destination_account_id": self.destination_account_id.id,
            "cash_transfer_pos_id": self.pos_session_id.id,
        }
        return self.env["account.payment"].create(default_values)

    def action_create_cash_transfer(self):
        self.pos_session_id._cash_transfer_sufficient_funds(self.amount)
        payment = self._create_cash_transfer_payment()
        activity_type = self._get_activity_type_for_cash_transfer()
        if not activity_type:
            _logger.info("Activity type not found")
            return
        self._schedule_activity(payment)
        action = {
            "name": _("Payments"),
            "type": "ir.actions.act_window",
            "res_model": "account.payment",
            "context": {"create": False},
            "view_mode": "form",
            "res_id": payment.id,
        }
        return action

    def _schedule_activity(self, payment):
        users = self._get_schedule_activity_users()
        for user in users:
            payment.activity_schedule(
                "marin.cash_transfer_activity",
                user_id=user.id,
                note=_("Cash Transfer"),
            )

    def _get_schedule_activity_users(self):
        job = self.env.ref("marin.hr_job_14")
        users = self.env["hr.employee"].search([("job_id", "=", job.id)]).mapped("user_id")
        return users or self.env.user

    @api.onchange("journal_id")
    def _onchange_currency_id(self):
        self.ensure_one()
        self.currency_id = self.journal_id.currency_id or self.journal_id.company_id.currency_id

    @api.onchange("destination_journal_id")
    def _compute_destination_account(self):
        self.ensure_one()
        self.destination_account_id = self.destination_journal_id.company_id.transfer_account_id.id
