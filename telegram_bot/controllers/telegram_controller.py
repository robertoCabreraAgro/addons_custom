import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class TelegramController(http.Controller):
    _command_handlers = {
        "/start": "_handle_start_command",
        "/ayuda": "_handle_help_command",
        "/quiensoy": "_handle_whoami_command",
    }

    _unlinked_user_cmds = {"/start", "/ayuda"}
    _partner_added_cmds = {"/quiensoy"}
    _internal_user_added_cmds = set()

    @http.route("/telegram/webhook/<string:token>", type="jsonrpc", auth="public", csrf=False)
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
                self._dispatch_message(bot, data["message"])
            elif "callback_query" in data:
                self._dispatch_callback_query(bot, data["callback_query"])

            return "OK"
        except Exception as e:
            _logger.error("Error processing webhook for bot '%s': %s", bot.name, e)
            return "Error"

    def _get_chat_and_user(self, bot, message_or_callback):
        """Factor out common logic to get chat, partner, and user."""
        is_callback = "data" in message_or_callback
        if is_callback:
            chat_id = message_or_callback["message"]["chat"]["id"]
            telegram_username = message_or_callback["from"].get("username")
        else:
            chat_id = message_or_callback["chat"]["id"]
            telegram_username = message_or_callback.get("from", {}).get("username")

        chat = request.env["telegram.chat"].sudo()._find_or_create(chat_id, bot.id, telegram_username)
        partner = chat.partner_id
        internal_user = partner.user_ids[0] if partner and partner.user_ids else False
        return chat, partner, internal_user

    def _dispatch_message(self, bot, message):
        """Handles regular messages (commands, text, photos)."""
        chat, partner, internal_user = self._get_chat_and_user(bot, message)

        # Flow of a command, meaning it start with "/"
        if message.get("text", "").startswith("/"):
            parts = message.get("text").split()
            command = parts[0].split("@")[0]
            args = parts[1:]
            self._dispatch_command(bot, chat, command, args, partner, internal_user)
        # Flow to manage an answer that is not a command (f.ex. a file)
        else:
            # This method can be override for children controllers
            self._handle_non_command_message(bot, chat, message, partner, internal_user)

    def _dispatch_callback_query(self, bot, callback_query):
        """Handles responses from inline keyboards."""
        chat, partner, internal_user = self._get_chat_and_user(bot, callback_query)
        # This method can be override for children controllers
        self._handle_callback_query(bot, chat, callback_query, partner, internal_user)

    def _dispatch_command(self, bot, chat, command, args, partner, internal_user):
        """Finds and calls the appropriate command handler based on user permissions."""
        handler_name = self._command_handlers.get(command)
        available_cmds = [cmd.name for cmd in bot.command_ids] + [
            "/start",
            "/ayuda",
            "/quiensoy",
        ]
        if not handler_name or command not in available_cmds:
            bot.send_message(
                chat.chat_id,
                f"Comando desconocido: `{command}`. Escribe /ayuda para más información.",
            )
            return

        handler_method = getattr(self, handler_name, None)
        if not handler_method:
            _logger.error("Handler '%s' not implemented in controller.", handler_name)
            return

        # Build hierarchically allowed commands
        allowed_cmds = self._unlinked_user_cmds.copy()
        if partner:
            allowed_cmds.update(self._partner_added_cmds)
        if internal_user:
            allowed_cmds.update(self._internal_user_added_cmds)

        # Centralized permission check
        if command not in allowed_cmds:
            if not partner:
                msg = (
                    f"Para usar el comando `{command}`, tu cuenta de Telegram debe estar vinculada. "
                    "Por favor, solicita que se realice la vinculación."
                )
            else:
                msg = f"No tienes permiso para usar el comando `{command}`."
            bot.send_message(chat.chat_id, msg)
            return

        # Dispatch the command with the correct context
        if internal_user:
            _logger.info(
                "Dispatching command '%s' as internal user %s",
                command,
                internal_user.name,
            )
            env_as_user = request.env(user=internal_user)
            # Re-browse records in the user's environment
            bot_as_user = bot.with_env(env_as_user)
            chat_as_user = chat.with_env(env_as_user)
            partner_as_user = partner.with_env(env_as_user)
            handler_method(
                bot_as_user,
                chat_as_user,
                args,
                partner=partner_as_user,
                internal_user=internal_user,
            )
        else:
            _logger.info(
                "Dispatching command '%s' as %s",
                command,
                partner.name if partner else "unlinked user",
            )
            handler_method(bot, chat, args, partner=partner, internal_user=internal_user)

    # --- Handlers that can be overriden ---

    def _handle_non_command_message(self, bot, chat, message, partner, internal_user):
        """Default handler for messages that are not commands."""
        bot.send_message(
            chat.chat_id,
            "Lo siento, solo puedo procesar comandos. Escribe /ayuda para ver la lista.",
        )

    def _handle_callback_query(self, bot, chat, callback_query, partner, internal_user):
        """Default handler for callback queries."""
        bot.send_message(chat.chat_id, "He recibido una acción, pero no sé cómo procesarla.")

    # --- Command Handlers ---

    def _handle_start_command(self, bot, chat, args, partner=False, internal_user=False):
        """Handles the /start command."""
        welcome_message = f"¡Bienvenido a *{bot.name}*!\nEscribe /ayuda para ver lo que puedo hacer."
        bot.send_message(chat.chat_id, welcome_message)

    def _handle_help_command(self, bot, chat, args, partner=False, internal_user=False):
        """Handles the /ayuda command based on the user's permission level."""
        base_cmds = ["*/ayuda* - Muestra este mensaje de ayuda."]
        partner_cmds = ["*/quiensoy* - Verifica tu identidad en Odoo."]

        help_parts = ["Comandos disponibles para ti:\n"]

        if partner:
            help_parts.extend(partner_cmds)

        help_parts.extend(base_cmds)
        bot.send_message(chat.chat_id, "\n".join(help_parts))

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
        else:  # No debería ocurrir por el chequeo de permisos, pero por si acaso.
            user_message = "Este chat no está vinculado a ningún contacto de Odoo."
        bot.send_message(chat.chat_id, user_message)
