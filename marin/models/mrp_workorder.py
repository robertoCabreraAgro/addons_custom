from odoo import fields, models


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    production_type = fields.Selection(
        related="production_id.production_type",
        string="Production Type",
        store=True,
        readonly=True,
    )
