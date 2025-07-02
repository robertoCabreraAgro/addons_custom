from odoo import fields, models


class TelegramCommand(models.Model):
    _name = "telegram.command"
    _description = "Telegram Command"

    name = fields.Char(required=True)
