# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    work_team_ids = fields.Many2many(
        "work.team",
        "work_team_member",
        "user_id",
        "work_team_id",
        string="Work Teams",
        check_company=True,
        compute="_compute_work_team_ids",
        readonly=True,
        search="_search_work_team_ids",
        copy=False,
    )
    work_team_member_ids = fields.One2many(
        "work.team.member",
        "user_id",
        string="Work Team Members",
    )
    work_team_id = fields.Many2one(
        "work.team",
        string="User Work Team",
        compute="_compute_work_team_id",
        store=True,
        readonly=True,
        help="Main user sales team. Used notably for pipeline, "
        "or to set sales team in invoicing or subscription.",
    )

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    @api.depends("work_team_member_ids.active")
    def _compute_work_team_ids(self):
        for user in self:
            user.work_team_ids = user.work_team_member_ids.work_team_id

    @api.depends(
        "work_team_member_ids.work_team_id",
        "work_team_member_ids.create_date",
        "work_team_member_ids.active",
    )
    def _compute_work_team_id(self):
        for user in self:
            if not user.work_team_member_ids.ids:
                user.work_team_id = False
            else:
                sorted_memberships = user.work_team_member_ids  # sorted by create date
                user.work_team_id = (
                    sorted_memberships[0].work_team_id if sorted_memberships else False
                )

    # ------------------------------------------------------------
    # SEARCH METHODS
    # ------------------------------------------------------------

    def _search_work_team_ids(self, operator, value):
        return [("work_team_member_ids.work_team_id", operator, value)]
