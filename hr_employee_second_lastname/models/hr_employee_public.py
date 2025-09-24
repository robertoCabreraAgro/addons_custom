from odoo import fields, models


class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    firstname = fields.Char("First name")
    lastname = fields.Char("Last name")
    lastname2 = fields.Char("Second last name")
