from odoo import fields, models


class Company(models.Model):
    _inherit = "res.company"


    port = fields.Char(
        "Port",
        help="This is the port where Odoo will listen",
    )
