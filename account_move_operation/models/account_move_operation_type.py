from odoo import fields, models


class AccountMoveType(models.Model):
    _name = "account.move.operation.type"
    _description = "Account Operation Types"
    _order = "sequence"
    _check_company_auto = True


    name = fields.Char("Type", required=True, translate=True)
    active = fields.Boolean(
        default=True,
        help="If unchecked, it will allow you to hide the action without removing it."
    )
    sequence = fields.Integer(default=0)
    company_ids = fields.Many2many(
        comodel_name='res.company',
        string='Companies',
        required=True,
        default=lambda self: self.env.company,
        readonly=False,
    )
    execution = fields.Selection(
        selection=[
            ("sequencial", "Sequencial"),
            ("async", "Asynchronous"),
        ],
        index=True,
    )
    action_ids = fields.One2many(
        comodel_name="account.move.operation.action",
        inverse_name="operation_type_id",
        string="Actions",
        copy=True,
    )
    from_bank_statement = fields.Boolean(
        help="Enable being set from a bank statement.",
    )
    sub_operation = fields.Boolean(
        help="This sets the operation to be used as a sub operation.",
    )
