from odoo import fields, models


class HrSchedulePayment(models.Model):
    _name = "hr.schedule.payment"
    _description = "Allows to configure the paydays and periods of the year for the payroll."

    name = fields.Char(
        required=True,
        translate=True,
        help="Name of the schedule payment.",
    )
    code = fields.Char(
        help="Code of the schedule payment.",
    )
    days_to_pay = fields.Float(
        help="Indicates the days to pay in the payroll.",
    )
    periods_per_year = fields.Float(
        help="Number of periods in the year according to the type of payment in the payroll.",
    )
