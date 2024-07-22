# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    purchase_user_id = fields.Many2one(
        "res.users",
        "Purchase representative",
        domain="[('share', '=', False)]",
        index=True,
    )
    purchase_team_id = fields.Many2one(
        "srm.team",
        "Purchase Team",
        help="If set, this Purchase Team will be used for purchases and assignments related to this partner",
    )
