import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class TelegramController(http.Controller):
    _command_handlers = {
        "/start": "_handle_start_command",
        "/help": "_handle_help_command",
        "/whoami": "_handle_whoami_command",
    }

    _unlinked_user_cmds = {"/start", "/help"}
    _partner_added_cmds = {"/whoami"}
    _internal_user_added_cmds = {}

    @http.route("/telegram/webhook/<string:token>", type="jsonrpc", auth="public", csrf=False, methods=["POST"])
    def webhook(self, token, **kwargs):
        """Main webhook entry point. Finds the bot and dispatches the message."""
        bot = request.env["telegram.bot"].sudo().search([("token", "=", token)], limit=1)
        if not bot:
            _logger.warning("Webhook called with an invalid token.")
            return "OK"

        try:
            data = json.loads(request.httprequest.data)
            _logger.info("Received update for bot '%s': %s", bot.name, data)

            if "message" in data:
                message = data["message"]
                chat_id = message["chat"]["id"]

                # When creating the chat, the linking Odoo-Telegram logic will be triggered
                telegram_username = message.get("from", {}).get("username")
                chat = request.env["telegram.chat"].sudo()._find_or_create(chat_id, bot.id, telegram_username)

                if message.get("text", "").startswith("/"):
                    parts = message.get("text").split()
                    command = parts[0].split("@")[0]
                    args = parts[1:]
                    self._dispatch_command(bot, chat, command, args)
                else:
                    bot.send_message(
                        chat_id, "Lo siento, solo puedo procesar comandos. Escribe /help para ver la lista."
                    )
            return "OK"
        except Exception as e:
            _logger.error("Error processing webhook for bot '%s': %s", bot.name, e)
            return "Error"

    def _dispatch_command(self, bot, chat, command, args):
        """Finds and calls the appropriate command handler based on user permissions."""
        handler_name = self._command_handlers.get(command)
        if not handler_name:
            bot.send_message(chat.chat_id, f"Comando desconocido: `{command}`. Escribe /help para más información.")
            return

        handler_method = getattr(self, handler_name)

        chat.invalidate_recordset(["partner_id"])
        partner = chat.partner_id
        internal_user = partner.user_ids[0] if partner and partner.user_ids else False

        # Build allowed commands hierarchically
        allowed_cmds = self._unlinked_user_cmds.copy()
        if partner:
            allowed_cmds.update(self._partner_added_cmds)
        if internal_user:
            allowed_cmds.update(self._internal_user_added_cmds)

        # Centralized permission check
        if command not in allowed_cmds:
            if not partner:
                # Provide a more helpful message if the user is not linked at all
                bot.send_message(
                    chat.chat_id,
                    f"Para usar el comando `{command}`, tu cuenta de Telegram debe estar vinculada a un contacto en Odoo. "
                    "Por favor, solicita que se realice la vinculación.",
                )
            else:
                # Generic permission denied message for linked partners
                bot.send_message(chat.chat_id, f"No tienes permiso para usar el comando `{command}`.")
            return

        # Dispatch the command with the correct context
        if internal_user:
            _logger.info("Dispatching command '%s' as internal user %s", command, internal_user.name)
            env_as_user = request.env(user=internal_user)
            bot_as_user = env_as_user["telegram.bot"].browse(bot.id)
            chat_as_user = env_as_user["telegram.chat"].browse(chat.id)
            handler_method(bot_as_user, chat_as_user, args, partner=partner, internal_user=internal_user)
        else:
            # This branch handles both linked partners and unlinked users
            if partner:
                _logger.info("Dispatching command '%s' as partner %s", command, partner.name)
            else:
                _logger.info("Dispatching command '%s' as unlinked user.", command)
            handler_method(bot, chat, args, partner=partner, internal_user=internal_user)

    # --- Command Handlers ---

    def _handle_start_command(self, bot, chat, args, partner=False, internal_user=False):
        """Handles the /start command."""
        welcome_message = f"¡Bienvenido a *{bot.name}*!\nEscribe /help para ver lo que puedo hacer."
        bot.send_message(chat.chat_id, welcome_message)

    def _handle_help_command(self, bot, chat, args, partner=False, internal_user=False):
        """Handles the /help command based on the user's permission level."""
        if internal_user:
            help_text = (
                "Comandos disponibles para ti:\n\n"
                "*/whoami* - Verifica tu identidad en Odoo.\n"
                "*/help* - Muestra este mensaje de ayuda."
            )
        elif partner:
            help_text = (
                "Comandos disponibles para ti:\n\n"
                "*/whoami* - Verifica con qué contacto de Odoo estás vinculado.\n"
                "*/help* - Muestra este mensaje de ayuda."
            )
        else:
            help_text = "Comandos disponibles para ti:\n\n*/help* - Muestra este mensaje de ayuda."
        bot.send_message(chat.chat_id, help_text)

    def _handle_whoami_command(self, bot, chat, args, partner=False, internal_user=False):
        """Verifies if the chat is linked to a partner/user and responds."""
        if internal_user:
            user_message = (
                f"Estás operando como el usuario de Odoo:\n"
                f"- *Nombre:* {internal_user.name}\n"
                f"- *Email:* {internal_user.login}"
            )
        elif partner:
            user_message = f"Este chat de Telegram está vinculado al contacto de Odoo:\n- *Nombre:* {partner.name}"
        bot.send_message(chat.chat_id, user_message)
