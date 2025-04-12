from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_load_all_partners_by_company = fields.Boolean(
        related="pos_config_id.load_all_partners_by_company", readonly=False
    )
