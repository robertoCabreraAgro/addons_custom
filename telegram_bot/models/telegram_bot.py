import json
import logging

import requests

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class TelegramBot(models.Model):
    _name = "telegram.bot"
    _description = "Telegram Bot Configuration"

    name = fields.Char(string="Bot Name", required=True)
    token = fields.Char(string="Bot Token", required=True, copy=False)
    chat_ids = fields.One2many("telegram.chat", "bot_id", string="Chats")
    payment_approval_category_id = fields.Many2one(
        "approval.category",
        string="Payment Approval Category",
        help="Category to be used for payment approval requests created from Telegram.",
    )
    command_ids = fields.Many2many(
        "telegram.command",
        string="Extra commands",
    )
    has_pago_command = fields.Boolean(
        compute="_compute_has_pago_command",
        store=True,
    )

    _token_uniq = models.Constraint(
        "UNIQUE (token)",
        "The bot token must be unique!",
    )

    @api.depends("command_ids")
    def _compute_has_pago_command(self):
        for bot in self:
            bot.has_pago_command = "/pago" in bot.command_ids.mapped("name")

    def _send_request(self, method, payload):
        """Helper to send request to the Telegram API."""
        self.ensure_one()
        api_url = f"https://api.telegram.org/bot{self.token}/{method}"
        try:
            response = requests.post(api_url, json=payload, timeout=10)
            response.raise_for_status()
            _logger.info(
                "Request '%s' sent to chat %s by bot '%s'.",
                method,
                payload.get("chat_id"),
                self.name,
            )
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error(
                "Failed to send request '%s' for bot '%s': %s", method, self.name, e
            )
            return False

    def send_message(self, chat_id, text):
        """Sends a message to a specific chat through the Telegram Bot API."""
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }
        return self._send_request("sendMessage", payload)

    def send_message_with_keyboard(self, chat_id, text, keyboard_buttons):
        """Sends a message with an inline keyboard.
        keyboard_buttons: A list of lists of dicts, e.g. [[{'text': 'OK', 'callback_data': 'ok'}]]
        """
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": json.dumps({"inline_keyboard": keyboard_buttons}),
        }
        return self._send_request("sendMessage", payload)

    def get_file_content(self, file_id):
        """Downloads the content of a file given its ID."""
        self.ensure_one()
        # 1. Get file path
        file_info = self._send_request("getFile", {"file_id": file_id})
        if not file_info or not file_info.get("ok"):
            _logger.error("Could not get file info for file_id %s", file_id)
            return False

        file_path = file_info["result"]["file_path"]

        # 2. Download file content
        file_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
        try:
            response = requests.get(file_url, timeout=15)
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException as e:
            _logger.error("Failed to download file from %s: %s", file_url, e)
            return False
