from odoo import fields, models


class PlanningCancelReason(models.Model):
    _name = "planning.cancel.reason"
    _inherit = ["mail.thread"]
    _description = "Planning Cancel Reason"
    _order = "sequence"

    active = fields.Boolean(string="Active", default=True)
    name = fields.Char(string="Name", required=True, translate=True)
    description = fields.Text(string="Description", translate=True)
    sequence = fields.Integer(default=10)
