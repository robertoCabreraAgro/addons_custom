from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    hr_schedule_payment_id = fields.Many2one(
        "hr.schedule.payment",
        string="Schedule Payment",
        related="current_version_id.hr_schedule_payment_id",
        readonly=False,
        help="Schedule payment according to the payment frequency.",
    )