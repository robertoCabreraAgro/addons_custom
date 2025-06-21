import base64
import logging
from datetime import datetime

from odoo import _
from odoo.exceptions import AccessError

from .telegram_controller import TelegramController

_logger = logging.getLogger(__name__)


class PaymentApprovalTelegramController(TelegramController):
    def __init__(self):
        """Extend the parent controller's handlers."""
        super().__init__()
        self._command_handlers.update(
            {
                "/pago": "_handle_payment_command",
                "/cancelarpago": "_handle_cancel_command",
            }
        )
        self._internal_user_added_cmds.add("/pago")
        self._internal_user_added_cmds.add("/cancelarpago")

    # --- Override the generic handlers to add our logic ---
    def _handle_non_command_message(self, bot, chat, message, partner, internal_user):
        """Handles multi-line payment data and the receipt of the proof document."""
        if chat.state == "awaiting_payment_details":
            self._process_payment_details(bot, chat, message, internal_user)
        elif chat.state == "awaiting_payment_proof":
            if message.get("photo"):
                self._handle_payment_proof_file(bot, chat, message, internal_user, is_photo=True)
            elif message.get("document"):
                document = message["document"]
                if document.get("mime_type") == "application/pdf":
                    self._handle_payment_proof_file(bot, chat, message, internal_user, is_photo=False)
                else:
                    bot.send_message(
                        chat.chat_id, "Tipo de documento invalido. Porfavor envia una imagen (JPEG/PNG) o un PDF."
                    )
            else:
                bot.send_message(chat.chat_id, "Porfavor envia una imagen (JPEG/PNG) o un PDF.")
        else:
            # If not in a specific state, use the parent's logic
            super()._handle_non_command_message(bot, chat, message, partner, internal_user)

    def _handle_callback_query(self, bot, chat, callback_query, partner, internal_user):
        """Handles the confirmation/cancellation buttons."""
        if chat.state != "awaiting_confirmation":
            return

        data = callback_query.get("data")
        if data == "payment_confirm":
            self._confirm_payment_approval(bot, chat, internal_user)
        elif data == "payment_cancel":
            chat.reset_state()
            bot.send_message(chat.chat_id, "Operación cancelada.")
        else:
            super()._handle_callback_query(bot, chat, callback_query, partner, internal_user)

    def _handle_help_command(self, bot, chat, args, partner=False, internal_user=False):
        """Override the help handler to add the new command. Now is /ayuda"""
        super()._handle_help_command(bot, chat, args, partner=partner, internal_user=internal_user)

        if internal_user:
            pago_help = (
                "*/pago* - Inicia el registro de un pago.\n"
                "Después de enviar el comando, el bot te pedirá que envíes los detalles del pago en un "
                "solo mensaje, con cada dato en una nueva línea, en el siguiente orden:\n\n"
                "1.  *A quién se factura*: Nombre (o parte del nombre) de un cliente existente.\n"
                "2.  *Categoría de producto*: `Agroquimicos` o `Papas`.\n"
                "3.  *Uso CFDI*: `Adquisicion de mercancias` o `Gastos en general`.\n"
                "4.  *Método de pago*: `Transferencia`, `Efectivo`, `TC` o `TD`.\n"
                "5.  *Compañía*: `LMMR` o `LMMG`.\n"
                "6.  *A quién se aplica el pago*: Nombre (o parte del nombre) de un cliente existente.\n"
                "7.  *Fecha de pago*: En formato `AAAA-MM-DD`.\n"
                "8.  *Monto*: Importe numérico (ej. `1500.50`).\n\n"
                "*/cancelarpago* - Cancela el proceso actual de registro de pago."
            )
            bot.send_message(chat.chat_id, pago_help)

    # --- Specific logic of /pago command ---
    def _handle_payment_command(self, bot, chat, args, partner=False, internal_user=False):
        """Process the /pago command and prepares for the multi-line message."""
        chat.write({"state": "awaiting_payment_details", "pending_payment_data": "{}"})
        bot.send_message(
            chat.chat_id,
            (
                "Por favor, envía los detalles del pago en 8 líneas separadas, siguiendo el formato indicado "
                "en /ayuda.\n\nPuedes usar /cancelarpago en cualquier momento para detener esta operación."
            ),
        )

    def _handle_cancel_command(self, bot, chat, args, partner=False, internal_user=False):
        """Cancels the current payment registration process."""
        cancellable_states = [
            "awaiting_payment_details",
            "awaiting_payment_proof",
            "awaiting_confirmation",
        ]
        if chat.state in cancellable_states:
            chat.reset_state()
            bot.send_message(chat.chat_id, "Operación de registro de pago cancelada.")
        else:
            bot.send_message(chat.chat_id, "No hay ninguna operación de pago en curso para cancelar.")

    # --- Validation Helper Methods ---
    def _normalize_string(self, string):
        """Converts to lowercase and removes common accents."""
        string = string.lower()
        replacements = str.maketrans("áéíóú", "aeiou")
        return string.translate(replacements)

    def _validate_partner(self, internal_user, partner_name, error_prefix):
        """Finds a unique partner based on a name."""
        try:
            partner_model = internal_user.env["res.partner"].with_user(internal_user)
            partners = partner_model.search([("name", "ilike", partner_name)])
            if not partners:
                return None, f"{error_prefix}: No se encontró ningún cliente que coincida con '{partner_name}'."
            if len(partners) > 1:
                found = ", ".join(p.name for p in partners[:5])
                msg = (
                    f"{error_prefix}: Se encontraron varios clientes para '{partner_name}': "
                    f"{found}. Por favor, sé más específico."
                )
                return None, msg
            return partners, None
        except AccessError:
            _logger.warning(
                "AccessError while searching for partner '%s' for user %s.", partner_name, internal_user.login
            )
            return None, "No tienes permisos para buscar clientes. Contacta a un administrador."

    def _validate_choice(self, value, valid_options, error_msg):
        """Validates a normalized value against a list of options."""
        if self._normalize_string(value) not in valid_options:
            return error_msg
        return None

    def _validate_date(self, date_str):
        """Validates a string is in YYYY-MM-DD format."""
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date(), None
        except ValueError:
            return None, f"El formato de fecha es incorrecto ('{date_str}'). Usa AAAA-MM-DD."

    def _validate_amount(self, amount_str):
        """Validates a string is a valid number."""
        try:
            return float(amount_str), None
        except ValueError:
            return None, f"El monto '{amount_str}' no es un número válido."

    # --- Main Processing Logic ---
    def _process_payment_details(self, bot, chat, message, internal_user):
        """Parses and validates the multi-line message with payment details."""
        lines = message.get("text", "").strip().split("\n")
        if len(lines) != 8:
            msg = (
                f"Error: Se esperaban 8 líneas, pero se recibieron {len(lines)}. "
                "Por favor, envía todos los datos en un solo mensaje, cada uno en una nueva línea. "
                "Usa /ayuda para ver el formato exacto."
            )
            bot.send_message(chat.chat_id, msg)
            return

        p_fx_name, category, cfdi, method, company, p_cn_name, date_str, amount_str = (line.strip() for line in lines)
        errors = []

        partner_fx, err = self._validate_partner(internal_user, p_fx_name, "A quién se factura")
        if err:
            errors.append(err)

        partner_cn, err = self._validate_partner(internal_user, p_cn_name, "A quién se aplica el pago")
        if err:
            errors.append(err)

        err = self._validate_choice(
            category,
            ["agroquimicos", "papas"],
            f"Categoría de producto inválida: '{category}'. Opciones: Agroquimicos, Papas.",
        )
        if err:
            errors.append(err)

        err = self._validate_choice(
            cfdi,
            ["adquisicion de mercancias", "gastos en general"],
            f"Uso de CFDI inválido: '{cfdi}'. Opciones: Adquisicion de mercancias, Gastos en general.",
        )
        if err:
            errors.append(err)

        err = self._validate_choice(
            method,
            ["transferencia", "efectivo", "tc", "td"],
            f"Método de pago inválido: '{method}'. Opciones: Transferencia, Efectivo, TC, TD.",
        )
        if err:
            errors.append(err)

        err = self._validate_choice(
            company, ["lmmr", "lmmg"], f"Compañía inválida: '{company}'. Opciones: LMMR, LMMG."
        )
        if err:
            errors.append(err)

        payment_date, err = self._validate_date(date_str)
        if err:
            errors.append(err)

        amount, err = self._validate_amount(amount_str)
        if err:
            errors.append(err)

        if errors:
            bot.send_message(
                chat.chat_id, "Se encontraron los siguientes errores:\n\n" + "\n".join(f"- {e}" for e in errors)
            )
            return

        pending_data = {
            "partner_fx_id": partner_fx.id,
            "partner_fx_name": partner_fx.name,
            "product_category": self._normalize_string(category).upper(),
            "cfdi_use": self._normalize_string(cfdi).upper(),
            "payment_method": self._normalize_string(method).upper(),
            "company": self._normalize_string(company).upper(),
            "partner_cn_id": partner_cn.id,
            "partner_cn_name": partner_cn.name,
            "date": payment_date.strftime("%Y-%m-%d"),
            "amount": amount,
        }
        chat.write(
            {
                "state": "awaiting_payment_proof",
                "pending_payment_data": pending_data,
            }
        )
        bot.send_message(
            chat.chat_id, "Datos validados. Por favor, envía ahora el comprobante de pago (imagen o PDF)."
        )

    def _handle_payment_proof_file(self, bot, chat, message, internal_user, is_photo):
        """Process the payment proof and ask for confirmation."""
        if is_photo:
            file_id = message["photo"][-1]["file_id"]
            file_mimetype = "image/jpeg"
        else:
            file_id = message["document"]["file_id"]
            file_mimetype = "application/pdf"

        file_content = bot.get_file_content(file_id)
        if not file_content:
            bot.send_message(chat.chat_id, "Error al descargar el archivo. Por favor, inténtalo de nuevo.")
            return

        pending_data = chat.pending_payment_data.copy()
        pending_data["file_b64"] = base64.b64encode(file_content).decode("ascii")
        pending_data["file_mimetype"] = file_mimetype

        chat.write({"state": "awaiting_confirmation", "pending_payment_data": pending_data})

        summary_text = (
            "Por favor, confirma los datos para crear la solicitud:\n\n"
            f"- *A quién se factura:* {pending_data['partner_fx_name']}\n"
            f"- *Categoría de producto:* {pending_data['product_category']}\n"
            f"- *Uso CFDI:* {pending_data['cfdi_use']}\n"
            f"- *Método de pago:* {pending_data['payment_method']}\n"
            f"- *Compañía:* {pending_data['company']}\n"
            f"- *A quién se aplica el pago:* {pending_data['partner_cn_name']}\n"
            f"- *Fecha:* {pending_data['date']}\n"
            f"- *Monto:* ${pending_data['amount']:,.2f}\n"
            "- *Comprobante:* (Archivo recibido)"
        )
        keyboard = [
            [
                {"text": "1. Confirmar", "callback_data": "payment_confirm"},
                {"text": "2. Cancelar", "callback_data": "payment_cancel"},
            ]
        ]
        bot.send_message_with_keyboard(chat.chat_id, summary_text, keyboard)

    def _confirm_payment_approval(self, bot, chat, internal_user):
        """Creates the approval request in Odoo."""
        if not bot.payment_approval_category_id:
            bot.send_message(
                chat.chat_id, "Error: El bot no tiene configurada una categoría para aprobaciones de pago."
            )
            chat.reset_state()
            return

        data = chat.pending_payment_data

        # Prepare a clean dict for the new JSON field, without file data.
        telegram_data = data.copy()
        telegram_data.pop("file_b64", None)
        telegram_data.pop("file_mimetype", None)

        approval_vals = {
            "category_id": bot.payment_approval_category_id.id,
            "request_owner_id": internal_user.id,
            "partner_id": data["partner_cn_id"],
            "date": data["date"],
            "amount": data["amount"],
            "telegram_data": telegram_data,
        }

        try:
            # 1. Create the approval request
            approval = internal_user.env["approval.request"].with_user(internal_user).create(approval_vals)

            # 2. Create the attachment
            attachment_name = f"comprobante_{data['partner_cn_name'].replace(' ', '_')}_{approval.id}.dat"
            attachment = (
                internal_user.env["ir.attachment"]
                .with_user(internal_user)
                .create(
                    {
                        "name": attachment_name,
                        "datas": data["file_b64"],
                        "res_model": "approval.request",
                        "res_id": approval.id,
                        "type": "binary",
                        "mimetype": data.get("file_mimetype", "application/octet-stream"),
                    }
                )
            )

            # 3. Call message_post with the ID of the attachment
            approval.message_post(body=_("Proof of payment attached from Telegram.", attachment_ids=[attachment.id]))

            # 4. Confirm request
            approval.action_confirm()

            # 5. Notify the user and clean state
            base_url = internal_user.env["ir.config_parameter"].sudo().get_param("web.base.url")
            message = f"¡Éxito! Se ha creado la solicitud de aprobación `{approval.name}`. /ayuda"

            if base_url:
                approval_url = f"{base_url}/web#id={approval.id}&" f"model=approval.request&view_type=form"
                markdown_link = f"[{approval.name}]({approval_url})"
                message = f"¡Éxito! Se ha creado la solicitud de aprobación: {markdown_link}. /ayuda"

            bot.send_message(chat.chat_id, message)
            chat.reset_state()

        except AccessError:
            _logger.error("AccessError para el usuario %s al crear la solicitud de aprobación.", internal_user.login)
            bot.send_message(chat.chat_id, "No tienes permiso para crear solicitudes de aprobación.")
            chat.reset_state()
        except Exception as e:
            _logger.error("Error al crear la solicitud de aprobación: %s", e)
            bot.send_message(chat.chat_id, "Ocurrió un error inesperado al crear la solicitud en Odoo.")
            chat.reset_state()
