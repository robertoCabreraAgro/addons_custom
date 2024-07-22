from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    not_global_entry = fields.Boolean(
        related="company_id.not_global_entry",
        readonly=False,
    )
