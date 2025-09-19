from odoo import fields, models


class RmaReason(models.Model):
    _name = "rma.reason"
    _description = "RMA Reason"

    name = fields.Char(string="Name", required=True)
    description = fields.Text(string="Description")
    sequence = fields.Integer(string="Sequence")
    active = fields.Boolean(string="Active", default=True)

    _unique_name = models.Constraint(
        "unique (name)",
        "The claim reason must be unique!",
    )
