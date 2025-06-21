import json
import logging

import requests

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

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

    _token_uniq = models.Constraint(
        "UNIQUE (token)",
        "The bot token must be unique!",
    )

    @api.constrains("token")
    def _onchange_token(self):
        """Validates the token by setting the webhook on Telegram's side.
        This method is automatically triggered on creation or update of the token.
        """
        for bot in self:
            if not bot.token:
                # If the token is cleared, we should try to remove the webhook
                bot._remove_webhook()
                continue

            base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
            if not base_url:
                raise ValidationError(
                    _(
                        "The system parameter 'web.base.url' is not set. "
                        "Please configure it in the System Parameters to set the Telegram webhook."
                    )
                )

            webhook_url = f"{base_url}/telegram/webhook/{bot.token}"
            api_url = f"https://api.telegram.org/bot{bot.token}/setWebhook"
            payload = {"url": webhook_url}

            _logger.info("Setting webhook for bot '%s' to URL: %s", bot.name, webhook_url)
            try:
                response = requests.post(api_url, data=payload, timeout=10)
                response.raise_for_status()
                result = response.json()

                if not result.get("ok"):
                    error_description = result.get("description", "Unknown error.")
                    _logger.error(
                        "Failed to set webhook for bot '%s'. Telegram API response: %s",
                        bot.name,
                        error_description,
                    )
                    raise ValidationError(f"Telegram API Error: {error_description}")

                _logger.info("Successfully set webhook for bot '%s'.", bot.name)

            except requests.exceptions.RequestException as e:
                _logger.error("Network error while setting webhook for bot '%s': %s", bot.name, e)
                raise ValidationError(f"Could not contact Telegram servers to set the webhook: {e}")

    def _remove_webhook(self, token=None):
        """Helper to remove the webhook from Telegram."""
        self.ensure_one()
        bot_token = token or self.token
        if not bot_token:
            return

        api_url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"
        _logger.info("Removing webhook for bot '%s'.", self.name)
        try:
            response = requests.post(api_url, timeout=10)
            response.raise_for_status()
            _logger.info("Successfully removed webhook for bot '%s'.", self.name)
        except requests.exceptions.RequestException as e:
            # We don't raise a ValidationError here as this might be called during deletion
            # where raising an error could prevent the record from being deleted.
            _logger.error("Failed to remove webhook for bot '%s': %s", self.name, e)

    def unlink(self):
        """On deletion, remove the webhook."""
        for bot in self:
            # We pass the token explicitly in case the record is already partially deleted
            bot._remove_webhook(token=bot.token)
        return super().unlink()

    def _send_request(self, method, payload):
        """Helper to send request to the Telegram API."""
        self.ensure_one()
        api_url = f"https://api.telegram.org/bot{self.token}/{method}"
        try:
            response = requests.post(api_url, json=payload, timeout=10)
            response.raise_for_status()
            _logger.info("Request '%s' sent to chat %s by bot '%s'.", method, payload.get("chat_id"), self.name)
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error("Failed to send request '%s' for bot '%s': %s", method, self.name, e)
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
