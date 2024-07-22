# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    is_membership_multi = fields.Boolean("Multi Teams", config_parameter="purchase_team.membership_multi")
