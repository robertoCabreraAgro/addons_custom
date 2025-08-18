from odoo import fields, models


class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    firstname = fields.Char()
    lastname = fields.Char()