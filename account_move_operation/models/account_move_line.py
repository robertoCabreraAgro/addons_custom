from odoo import models, fields


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    operation_id = fields.Many2one(
        related="move_id.operation_id",
        store=True,
        string="Move Operation",
    )
