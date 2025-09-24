import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class TelegramChat(models.Model):
    _name = "telegram.chat"
    _description = "Telegram Chat Session"

    chat_id = fields.Char(string="Chat ID", required=True, index=True, readonly=True)
    telegram_username = fields.Char(index=True, readonly=True)
    bot_id = fields.Many2one(
        "telegram.bot", string="Bot", required=True, readonly=True, ondelete="cascade"
    )
    partner_id = fields.Many2one("res.partner", string="Odoo Contact")
    state = fields.Selection(
        [
            ("idle", "Idle"),
            ("awaiting_payment_details", "Awaiting Payment Details"),
            ("awaiting_payment_proof", "Awaiting Payment Proof"),
            ("awaiting_confirmation", "Awaiting Confirmation"),
        ],
        string="Status",
        default="idle",
        required=True,
    )
    pending_payment_data = fields.Json(string="Pending Payment Data (JSON)")

    _chat_id_bot_id_uniq = models.Constraint(
        "UNIQUE (chat_id, bot_id)",
        "A chat ID must be unique per bot!",
    )

    _telegram_username_bot_id_uniq = models.Constraint(
        "UNIQUE (telegram_username, bot_id)",
        "A Telegram username must be unique per bot!",
    )

    @api.model
    def _find_or_create(self, chat_id, bot_id, telegram_username=None):
        """Finds an existing chat record or creates a new one."""
        chat_id_str = str(chat_id)
        domain = [("chat_id", "=", chat_id_str), ("bot_id", "=", bot_id)]
        chat = self.search(domain, limit=1)
        if not chat:
            chat = self.create(
                {
                    "chat_id": chat_id_str,
                    "bot_id": bot_id,
                    "telegram_username": telegram_username,
                }
            )
        elif chat.telegram_username != telegram_username:
            chat.telegram_username = telegram_username
        elif chat.partner_id and chat.partner_id.telegram_username != telegram_username:
            chat.partner_id.sudo().write({"telegram_username": telegram_username})
        return chat

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to attempt auto-linking new chats to partners."""
        chats = super().create(vals_list)
        for chat in chats.filtered(lambda c: not c.partner_id and c.telegram_username):
            # Search for a partner with a matching telegram_username for the same bot
            partner = self.env["res.partner"].search(
                [
                    ("telegram_username", "=", chat.telegram_username),
                ],
            )
            if partner:
                chat.partner_id = partner.id
                _logger.info(
                    "Automatically linked new chat %s to partner %s (ID: %s) via username '%s'.",
                    chat.id,
                    partner.name,
                    partner.id,
                    chat.telegram_username,
                )
        return chats

    def write(self, vals):
        """Overriide write to update partner's telegram_username if chat's username changes."""
        res = super().write(vals)
        if "partner_id" in vals:
            for chat in self:
                existing_partner = self.env["res.partner"].search(
                    [("telegram_username", "=", chat.telegram_username)]
                )
                if existing_partner:
                    existing_partner.write({"telegram_username": False})

                existing_partner.invalidate_recordset()
                chat.partner_id.write({"telegram_username": chat.telegram_username})
                _logger.info(
                    "Updated telegram_username on partner %s (ID: %s) to '%s' from chat %s via write.",
                    chat.partner_id.name,
                    chat.partner_id.id,
                    chat.telegram_username,
                    chat.id,
                )
        return res

    def reset_state(self):
        """Resets the chat state to idle."""
        self.write({"state": "idle", "pending_payment_data": False})
