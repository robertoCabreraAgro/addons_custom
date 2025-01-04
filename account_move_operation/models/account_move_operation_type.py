from odoo import fields, models


class AccountMoveType(models.Model):
    _name = "account.move.operation.type"
    _description = "Account Operation Types"
    _order = "sequence"
    _check_company_auto = True

    name = fields.Char("Type", required=True, translate=True)
    active = fields.Boolean(
        default=True,
        help="If the active field is set to False, it will allow you to hide the type without removing it.",
    )
    sequence = fields.Integer(default=0)
    action_ids = fields.One2many("account.move.operation.action", "operation_type_id", "Actions", copy=True)
    company_id = fields.Many2one(
        "res.company", "Company", default=lambda self: self.env.company, index=True, required=True
    )
    from_bank_statement = fields.Boolean(help="Enable being set from a bank statement.")
    sub_operation = fields.Boolean(help="This sets the operation to be used as a sub operation.")
