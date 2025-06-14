import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    telegram_username = fields.Char(copy=False)

    _telegram_username_uniq = models.Constraint(
        "UNIQUE (telegram_username)",
        "This Telegram username is already in use by another contact!",
    )

    def write(self, vals):
        """Override write to attempt auto-linking chats when telegram_username is set."""
        res = super().write(vals)
        if "telegram_username" in vals and vals["telegram_username"]:
            for partner in self:
                unlinked_chat = self.env["telegram.chat"].search(
                    [
                        ("telegram_username", "=", partner.telegram_username),
                        ("partner_id", "=", False),
                    ],
                    limit=1,
                )
                if unlinked_chat:
                    unlinked_chat.partner_id = partner.id
                    _logger.info(
                        "Automatically linked partner %s (ID: %s) to chat %s via username '%s' on partner update.",
                        partner.name,
                        partner.id,
                        unlinked_chat.id,
                        partner.telegram_username,
                    )
        return res
