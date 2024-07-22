from odoo import fields, models


class HrEmployeeDisciplinaryWarning(models.Model):
    _name = "hr.employee.disciplinary.warning"
    _description = """Employee Disciplinary Warnings, model to register them."""
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char("Title", required=True, tracking=True)
    active = fields.Boolean(
        default=True,
        tracking=True,
        help="If active, the action will be displayed.",
    )
    employee_id = fields.Many2one(
        "hr.employee",
        required=True,
        help="Who made the infraction to win this warning?",
    )
    date = fields.Date(
        tracking=True,
        required=True,
        help="Date when the infraction was made and the disciplinary warning applied.",
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        readonly=True,
    )
    disciplinary_action_id = fields.Many2one(
        "hr.leave",
        copy=False,
        help="Register if this disciplinary warning triggers a disciplinary action, a day off "
        "without pay, for example.",
    )
    notes = fields.Html()
