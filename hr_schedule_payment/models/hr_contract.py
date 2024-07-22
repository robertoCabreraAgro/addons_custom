from odoo import fields, models


class HrContract(models.Model):
    _inherit = "hr.contract"

    hr_schedule_payment_id = fields.Many2one(
        "hr.schedule.payment",
        string="Schedule Payment",
        help="Schedule payment, according to its schedule pay",
    )
