# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    srm_team_member_ids = fields.One2many("srm.team.member", "user_id", "Purchases Team Members")
    srm_team_ids = fields.Many2many(
        "srm.team",
        "res_users_srm_team_rel",
        "user_id",
        "srm_team_id",
        "Purchases Teams",
        check_company=True,
        copy=False,
        compute="_compute_srm_team_ids",
        readonly=True,
        search="_search_srm_team_ids",
    )
    purchase_team_id = fields.Many2one(
        "srm.team",
        "User Purchases Team",
        compute="_compute_purchase_team_id",
        store=True,
        readonly=True,
        help="Main user purchases team. Used notably for pipeline, or to set purchases team in bills.",
    )

    @api.depends("srm_team_member_ids.active")
    def _compute_srm_team_ids(self):
        for user in self:
            user.srm_team_ids = user.srm_team_member_ids.srm_team_id

    def _search_srm_team_ids(self, operator, value):
        return [("srm_team_member_ids.srm_team_id", operator, value)]

    @api.depends("srm_team_member_ids.srm_team_id", "srm_team_member_ids.create_date", "srm_team_member_ids.active")
    def _compute_purchase_team_id(self):
        for user in self:
            if not user.srm_team_member_ids.ids:
                user.purchase_team_id = False
            else:
                sorted_memberships = user.srm_team_member_ids
                user.purchase_team_id = sorted_memberships[0].srm_team_id if sorted_memberships else False
