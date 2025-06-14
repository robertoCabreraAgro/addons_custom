import logging

import requests

from odoo import fields, models

_logger = logging.getLogger(__name__)


class TelegramBot(models.Model):
    _name = "telegram.bot"
    _description = "Telegram Bot Configuration"

    name = fields.Char(string="Bot Name", required=True)
    token = fields.Char(string="Bot Token", required=True, copy=False)
    chat_ids = fields.One2many("telegram.chat", "bot_id", string="Chats")

    _token_uniq = models.Constraint(
        "UNIQUE (token)",
        "The bot token must be unique!",
    )

    def send_message(self, chat_id, text):
        """Sends a message to a specific chat through the Telegram Bot API."""
        self.ensure_one()
        api_url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }
        try:
            response = requests.post(api_url, json=payload, timeout=10)
            response.raise_for_status()
            _logger.info("Message sent to chat %s by bot '%s'.", chat_id, self.name)
        except requests.exceptions.RequestException as e:
            _logger.error("Failed to send message for bot '%s': %s", self.name, e)
