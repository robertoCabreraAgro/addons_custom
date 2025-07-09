import logging
from datetime import datetime

import pytz

from odoo.exceptions import ValidationError
from odoo.http import request

from .telegram_controller import TelegramController

_logger = logging.getLogger(__name__)

# Set the default timezone for Mexico City
DEFAULT_TZ = "America/Mexico_City"


class HrAttendanceTelegramController(TelegramController):
    def __init__(self):
        """Extend the parent controller's handlers to include attendance commands."""
        super().__init__()
        # Add new command handlers to the dispatcher
        self._command_handlers.update(
            {
                "/entrada": "_handle_check_in_command",
                "/salida": "_handle_check_out_command",
                "/comida": "_handle_lunch_out_command",
                "/regresocomida": "_handle_lunch_in_command",
            }
        )
        # Register commands that require the user to be a partner
        self._partner_added_cmds.update(
            [
                "/entrada",
                "/salida",
                "/comida",
                "/regresocomida",
            ]
        )

    def _validate_employee_access(self, bot, chat, partner):
        """Validates that the partner is an employee and can access attendance commands.

        :param bot: The telegram bot instance
        :param chat: The telegram chat instance
        :param partner: The partner to validate
        :return: True if valid employee, False otherwise
        """
        if not partner:
            bot.send_message(chat.chat_id, "Tu chat debe estar vinculado a un contacto para usar comandos de asistencia.")
            return False

        if not partner.sudo().employee_ids:
            bot.send_message(chat.chat_id, "Solo los empleados pueden usar comandos de asistencia.")
            return False

        return True

    def _parse_time_argument(self, args, user_tz_str, base_date_utc=None):
        """Parses an optional time argument from a command.
        If a valid HH:MM time is provided, it returns the corresponding datetime object for today in UTC.
        If no time is provided, it returns the current time in UTC.
        If the format is invalid, it returns an error message string.

        :param args: List of arguments from the command.
        :param user_tz_str: The IANA timezone string for the user.
        :param base_date_utc: An optional naive UTC datetime to use as the base date. If None, current date is used.
        :return: A tuple (datetime_utc, error_message). One of them will be None.
        """
        try:
            user_tz = pytz.timezone(user_tz_str)
        except pytz.UnknownTimeZoneError:
            user_tz = pytz.timezone(DEFAULT_TZ)

        now_user_tz = datetime.now(user_tz)
        if base_date_utc:
            # A base date was provided (e.g., a check-in from a previous day).
            # We use its date but combine it with the current time (or the time from args).
            base_dt_user_tz = pytz.utc.localize(base_date_utc).astimezone(user_tz)
            # Default to the old date with the current time.
            target_dt_user_tz = base_dt_user_tz.replace(
                hour=now_user_tz.hour, minute=now_user_tz.minute, second=now_user_tz.second, microsecond=0
            )
        else:
            # No base date, so we use today's date and the current time.
            target_dt_user_tz = now_user_tz.replace(microsecond=0)

        if args:
            time_str = args[0]
            try:
                # Parse the time string HH:MM
                time_parts = time_str.split(":")
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                # Create a new datetime object with today's date and the provided time.
                # The base (target_dt_user_tz) already has seconds/microseconds cleared.
                target_dt_user_tz = target_dt_user_tz.replace(hour=hour, minute=minute)
            except (ValueError, IndexError):
                error_msg = (
                    f"El formato de hora '{time_str}' es inválido. Por favor, usa el formato HH:MM (ej. 17:00)."
                )
                return None, error_msg

        # Always convert from the user's timezone to a naive UTC datetime
        return target_dt_user_tz.astimezone(pytz.utc).replace(tzinfo=None), None

    def _get_last_attendance(self, partner, internal_user):
        """Finds the latest open attendance record for the given partner.
        An open attendance is one that has a check_in but no check_out.

        :param partner: The partner for whom to find the attendance record.
        :param internal_user: The user of the partner.
        :return: The hr.attendance record if found, otherwise None.
        """
        if not partner or not partner.sudo().employee_ids:
            return None

        # Search for an attendance record for the current partner that
        # has not been checked out yet.
        attendance = request.env["hr.attendance"].sudo()
        return attendance.search(
            [
                ("employee_id", "=", partner.sudo().employee_ids[0].id),
                ("check_out", "=", False),
            ],
            limit=1,
            order="check_in desc",
        )

    def _handle_check_in_command(self, bot, chat, args, partner=False, internal_user=False):
        """Handles the /entrada command to record a check-in for the user."""
        if not self._validate_employee_access(bot, chat, partner):
            return

        user_tz_str = (internal_user and internal_user.tz) or DEFAULT_TZ
        check_in_time, error = self._parse_time_argument(args, user_tz_str)
        if error:
            bot.send_message(chat.chat_id, error)
            return

        # Find the latest attendance for today to check its status
        latest_attendance = self._get_last_attendance(partner, internal_user)
        if latest_attendance.check_in:
            bot.send_message(chat.chat_id, "Ya tienes una entrada registrada sin salida el día de hoy.")
            return

        try:
            # Create a new attendance record
            attendance = request.env["hr.attendance"].sudo()
            attendance.create(
                {
                    "employee_id": partner.sudo().employee_ids[0].id,
                    "check_in": check_in_time,
                }
            )
            formatted_time = check_in_time.astimezone(pytz.timezone(user_tz_str)).strftime("%H:%M")
            user_name = internal_user.name if internal_user else partner.name
            bot.send_message(
                chat.chat_id,
                f"¡Hola {user_name}! Se ha registrado tu entrada a las {formatted_time}. ¡Que tengas un excelente día!",
            )
        except ValidationError as e:
            new_attendance = attendance.search(
                [
                    ("employee_id", "=", partner.sudo().employee_ids[0].id),
                    ("check_in", "=", check_in_time),
                    ("check_out", "=", False),
                ]
            )
            new_attendance.unlink()
            bot.send_message(chat.chat_id, f"Error: {e}")

    def _handle_check_out_command(self, bot, chat, args, partner=False, internal_user=False):
        """Handles the /salida command to record a check-out for the user."""
        if not self._validate_employee_access(bot, chat, partner):
            return

        attendance = self._get_last_attendance(partner, internal_user)
        if not attendance.check_in:
            bot.send_message(chat.chat_id, "No tienes una entrada abierta para registrar una salida.")
            return
        user_tz_str = (internal_user and internal_user.tz) or DEFAULT_TZ
        check_out_time, error = self._parse_time_argument(args, user_tz_str, base_date_utc=attendance.check_in)
        if error:
            bot.send_message(chat.chat_id, error)
            return
        try:
            # Update the attendance record with the check-out time
            attendance.write({"check_out": check_out_time})
            formatted_time = check_out_time.astimezone(pytz.timezone(user_tz_str)).strftime("%H:%M")
            user_name = internal_user.name if internal_user else partner.name
            bot.send_message(
                chat.chat_id, f"Se ha registrado tu salida a las {formatted_time}. ¡Hasta luego, {user_name}!"
            )
        except ValidationError as e:
            attendance.write({"check_out": False})
            bot.send_message(chat.chat_id, f"Error: {e}")

    def _handle_lunch_out_command(self, bot, chat, args, partner=False, internal_user=False):
        """Handles the /comida command to record the start of a lunch break."""
        if not self._validate_employee_access(bot, chat, partner):
            return

        user_tz_str = (internal_user and internal_user.tz) or DEFAULT_TZ
        lunch_out_time, error = self._parse_time_argument(args, user_tz_str)
        if error:
            bot.send_message(chat.chat_id, error)
            return

        attendance = self._get_last_attendance(partner, internal_user)
        if not attendance.check_in:
            bot.send_message(chat.chat_id, "Debes tener una entrada activa para registrar tu salida a comer.")
            return

        if attendance.lunch_out:
            bot.send_message(chat.chat_id, "Ya has registrado tu salida a comer.")
            return
        # Update the attendance record with the lunch start time
        attendance.write({"lunch_out": lunch_out_time})
        formatted_time = lunch_out_time.astimezone(pytz.timezone(user_tz_str)).strftime("%H:%M")
        bot.send_message(chat.chat_id, f"Se ha registrado tu salida a comer a las {formatted_time}. ¡Buen provecho!")

    def _handle_lunch_in_command(self, bot, chat, args, partner=False, internal_user=False):
        """Handles the /regresocomida command to record the end of a lunch break."""
        if not self._validate_employee_access(bot, chat, partner):
            return

        user_tz_str = (internal_user and internal_user.tz) or DEFAULT_TZ
        lunch_in_time, error = self._parse_time_argument(args, user_tz_str)
        if error:
            bot.send_message(chat.chat_id, error)
            return

        attendance = self._get_last_attendance(partner, internal_user)
        if not attendance.check_in or not attendance.lunch_out:
            bot.send_message(
                chat.chat_id, "No has registrado una salida a comer, por lo que no puedes registrar tu regreso."
            )
            return

        if attendance.lunch_in:
            bot.send_message(chat.chat_id, "Ya has registrado tu regreso de la comida.")
            return

        try:
            # Update the attendance record with the lunch end time
            attendance.write({"lunch_in": lunch_in_time})
            formatted_time = lunch_in_time.astimezone(pytz.timezone(user_tz_str)).strftime("%H:%M")
            bot.send_message(chat.chat_id, f"Se ha registrado tu regreso de la comida a las {formatted_time}.")
        except ValidationError as e:
            attendance.write({"lunch_in": False})
            bot.send_message(chat.chat_id, f"Error: {e}")

    def _handle_help_command(self, bot, chat, args, partner=False, internal_user=False):
        """Extends the base help command to include attendance-related commands."""
        res = super()._handle_help_command(bot, chat, args, partner=partner, internal_user=internal_user)
        available_cmds = [cmd.name for cmd in bot.command_ids]

        if partner and partner.sudo().employee_ids and "/entrada" in available_cmds:
            attendance_help = [
                "\n*Comandos de Asistencia:*",
                "*/entrada [HH:MM]* - Registra tu llegada. Opcionalmente puedes especificar la hora.",
                "*/salida [HH:MM]* - Registra tu salida. Opcionalmente puedes especificar la hora.",
                "*/comida [HH:MM]* - Registra el inicio de tu comida. Opcionalmente puedes especificar la hora.",
                "*/regresocomida [HH:MM]* - Registra tu regreso de la comida. Opcionalmente puedes especificar la hora.",
            ]
            bot.send_message(chat.chat_id, "\n".join(attendance_help))
        return res
