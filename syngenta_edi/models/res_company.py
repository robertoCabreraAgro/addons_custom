from odoo import fields, models


class Company(models.Model):
    _inherit = "res.company"


    syngenta_customer_code = fields.Char(
        "Syngenta customer code",
        help="This is the identifier that this company has with Syngenta",
    )
    syngenta_demo = fields.Boolean(
        default=True,
        help="Especifies if the current enviroment is in demo state, the data sent "
             "in this state is not real.",
    )
