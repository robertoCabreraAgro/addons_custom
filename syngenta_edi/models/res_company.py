from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    syngenta_customer_code = fields.Char("Syngenta customer code")
    syngenta_demo = fields.Boolean(default=True)
