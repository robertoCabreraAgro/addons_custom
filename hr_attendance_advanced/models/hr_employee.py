from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    exempt_absence_for_delay = fields.Boolean(
        string="Exempt from Absences for Delay",
        help="Indicates if the employee is exempt from generating absences due to delays.",
    )
