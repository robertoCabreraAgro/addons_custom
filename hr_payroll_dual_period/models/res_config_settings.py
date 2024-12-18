from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    show_secondary_date_fields = fields.Boolean(
        related="company_id.show_secondary_date_fields",
        readonly=False,
    )
