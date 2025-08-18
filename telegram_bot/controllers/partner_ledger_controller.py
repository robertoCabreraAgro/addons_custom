import base64
import logging
from datetime import datetime

from odoo.exceptions import AccessError, ValidationError

from .telegram_controller import TelegramController

_logger = logging.getLogger(__name__)


class PartnerLedgerController(TelegramController):
    def __init__(self):
        super().__init__()
        # Register the estadocuenta command handler
        self._command_handlers.update(
            {
                "/estadocuenta": "_handle_estadocuenta_command",
            }
        )
        # Add command to partner-level permissions (customers can use it)
        self._partner_added_cmds.add("/estadocuenta")

    def _handle_estadocuenta_command(
        self, bot, chat, args, partner=False, internal_user=False
    ):
        """Handles the /estadocuenta command to generate Partner Ledger report.

        Usage:
            /estadocuenta - Generate report for current year
            /estadocuenta YYYY-MM-DD YYYY-MM-DD - Generate report for specific date range
        """
        if not self._validate_partner_access(bot, chat, partner):
            return

        try:
            # Parse date parameters
            date_from, date_to = self._parse_date_parameters(args)

            # Generate and send the Partner Ledger report
            self._generate_and_send_report(bot, chat, partner, date_from, date_to)

        except ValidationError as e:
            bot.send_message(chat.chat_id, f"Error en los parámetros: {str(e)}")
        except AccessError:
            bot.send_message(
                chat.chat_id,
                "No tienes permisos para generar este reporte. Contacta al administrador.",
            )
        except Exception as e:
            _logger.error(
                "Error generating partner ledger for partner %s: %s", partner.id, str(e)
            )
            bot.send_message(
                chat.chat_id,
                "Ocurrió un error al generar el estado de cuenta. Por favor, inténtalo más tarde.",
            )

    def _validate_partner_access(self, bot, chat, partner):
        """Validates that the user has the required access to generate Partner Ledger.

        Args:
            bot: Telegram bot instance
            chat: Telegram chat instance
            partner: Partner record

        Returns:
            bool: True if access is valid, False otherwise
        """
        # Check if partner has transactions in receivable or payable accounts
        # (the accounts that appear in Partner Ledger report)
        move_lines = bot.env["account.move.line"].search(
            [
                ("partner_id", "=", partner.id),
                ("display_type", "not in", ("line_section", "line_note")),
                (
                    "account_id.account_type",
                    "in",
                    ["asset_receivable", "liability_payable"],
                ),
                ("move_id.state", "=", "posted"),
            ],
            limit=1,
        )

        if not move_lines:
            bot.send_message(
                chat.chat_id,
                "No se encontraron transacciones de cuentas por cobrar o por pagar para tu cuenta.",
            )
            return False

        return True

    def _parse_date_parameters(self, args):
        """Parses date parameters from command arguments.

        Args:
            args: List of command arguments

        Returns:
            tuple: (date_from, date_to) as strings in 'YYYY-MM-DD' format

        Raises:
            ValidationError: If date parameters are invalid
        """
        if not args:
            # Default to current year
            current_year = datetime.now().year
            date_from = f"{current_year}-01-01"
            date_to = f"{current_year}-12-31"
        elif len(args) == 2:
            # Validate date format
            try:
                datetime.strptime(args[0], "%Y-%m-%d")
                datetime.strptime(args[1], "%Y-%m-%d")
                date_from = args[0]
                date_to = args[1]

                # Validate date range
                if date_from > date_to:
                    raise ValidationError(
                        "La fecha de inicio debe ser anterior a la fecha final."
                    )

            except ValueError:
                raise ValidationError(
                    "Formato de fecha inválido. Usa: /estadocuenta YYYY-MM-DD YYYY-MM-DD"
                )
        else:
            raise ValidationError(
                "Uso incorrecto. Usa: /estadocuenta o /estadocuenta YYYY-MM-DD YYYY-MM-DD"
            )

        return date_from, date_to

    def _generate_and_send_report(self, bot, chat, partner, date_from, date_to):
        """Generates the Partner Ledger report and sends it as PDF via Telegram.

        Args:
            bot: Telegram bot instance
            chat: Telegram chat instance
            partner: Partner record
            date_from: Start date string
            date_to: End date string
        """
        # Send initial message
        bot.send_message(
            chat.chat_id,
            f"Generando estado de cuenta para el período {date_from} al {date_to}...\n"
            "Por favor espera un momento.",
        )

        try:
            # Get the correct company for the partner (marin_data.company_lmmr)
            target_company = bot.env.ref(
                "marin_data.company_lmmr", raise_if_not_found=False
            )
            if not target_company:
                # Fallback to finding LMMR company by name
                target_company = bot.env["res.company"].search(
                    [("name", "ilike", "LMMR")], limit=1
                )

            if not target_company:
                raise Exception("No se pudo encontrar la empresa LMMR")

            # Get the Partner Ledger report with sudo permissions
            report = bot.env.ref("account_reports.partner_ledger_report").sudo()

            # Switch the report to the target company context
            report = report.with_context(allowed_company_ids=[target_company.id])

            # Configure report options with the correct company
            options = report.get_options(
                previous_options={
                    "forced_companies": [target_company.id],
                    "partner_ids": [partner.id],
                    "date": {"date_from": date_from, "date_to": date_to},
                    "export_mode": "print",
                    "unfold_all": True,
                }
            )

            # Generate PDF
            pdf_result = report.export_to_pdf(options)

            if not pdf_result or "file_content" not in pdf_result:
                raise Exception("No se pudo generar el archivo PDF")

            # Prepare file for sending
            file_name = f"Estado_Cuenta_{partner.name.replace(' ', '_')}_{date_from}_al_{date_to}.pdf"

            # Debug: Check if PDF content is valid
            pdf_content_b64 = pdf_result["file_content"]
            if isinstance(pdf_content_b64, str):
                file_content = base64.b64decode(pdf_content_b64)
            else:
                # If it's already bytes, use directly
                file_content = pdf_content_b64

            # Verify PDF header
            if not file_content.startswith(b"%PDF"):
                _logger.error(
                    "Generated content is not a valid PDF. First 20 bytes: %s",
                    file_content[:20],
                )
                raise Exception("El contenido generado no es un PDF válido")

            # Send PDF via Telegram
            bot.send_document(
                chat.chat_id,
                file_content,
                file_name,
                caption=f"Estado de cuenta para *{partner.name}*\nPeríodo: {date_from} al {date_to}",
            )

            _logger.info(
                "Partner Ledger report sent successfully to partner %s via Telegram",
                partner.id,
            )

        except Exception as e:
            _logger.error("Error in report generation: %s", str(e))
            raise

    def _handle_help_command(self, bot, chat, args, partner=False, internal_user=False):
        """Extends the base help command to include Partner Ledger command."""
        res = super()._handle_help_command(
            bot, chat, args, partner=partner, internal_user=internal_user
        )
        available_cmds = [cmd.name for cmd in bot.command_ids]

        if partner and "/estadocuenta" in available_cmds:
            estadocuenta_help = [
                "*/estadocuenta* - Obtén tu estado de cuenta del año actual.",
                "*/estadocuenta YYYY-MM-DD YYYY-MM-DD* - Estado de cuenta para fechas específicas.",
                "\nEjemplo: `/estadocuenta 2024-01-01 2024-06-30` para el primer semestre de 2024.",
            ]
            bot.send_message(chat.chat_id, "\n".join(estadocuenta_help))

        return res
