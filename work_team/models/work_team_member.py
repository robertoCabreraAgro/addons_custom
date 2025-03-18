# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, exceptions, fields, models, _


class CrmTeamMember(models.Model):
    _name = "work.team.member"
    _inherit = ["mail.thread"]
    _description = "Work Team Member"
    _rec_name = "user_id"
    _order = "create_date ASC, id"
    _check_company_auto = True

    work_team_id = fields.Many2one(
        "work.team",
        string="Work Team",
        required=True,
        default=False,  # TDE: temporary fix to activate depending computed fields
        check_company=True,
        group_expand="_read_group_expand_full",  # Always display all the teams
        ondelete="cascade",
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",  # TDE FIXME check responsible field
        required=True,
        check_company=True,
        domain="[('share', '=', False), ('id', 'not in', user_in_teams_ids), ('company_ids', 'in', user_company_ids)]",
        ondelete="cascade",
        index=True,
    )
    user_in_teams_ids = fields.Many2many(
        "res.users",
        compute="_compute_user_in_teams_ids",
        help="UX: Give users not to add in the currently chosen team to avoid duplicates",
    )
    user_company_ids = fields.Many2many(
        "res.company",
        compute="_compute_user_company_ids",
        help="UX: Limit to team company or all if no company",
    )
    active = fields.Boolean(string="Active", default=True)
    is_membership_multi = fields.Boolean(
        "Multiple Memberships Allowed",
        compute="_compute_is_membership_multi",
        help="If True, users may belong to several sales teams. "
        "Otherwise membership is limited to a single sales team.",
    )
    member_warning = fields.Text(compute="_compute_member_warning")
    # salesman information
    image_1920 = fields.Image(
        "Image", related="user_id.image_1920", max_width=1920, max_height=1920
    )
    image_128 = fields.Image(
        "Image (128)", related="user_id.image_128", max_width=128, max_height=128
    )
    name = fields.Char(string="Name", related="user_id.display_name", readonly=False)
    email = fields.Char(string="Email", related="user_id.email")
    phone = fields.Char(string="Phone", related="user_id.phone")
    mobile = fields.Char(string="Mobile", related="user_id.mobile")
    company_id = fields.Many2one(
        "res.company", string="Company", related="user_id.company_id"
    )

    @api.constrains("work_team_id", "user_id", "active")
    def _constrains_membership(self):
        # In mono membership mode: check work_team_id / user_id is unique for active
        # memberships. Inactive memberships can create duplicate pairs which is whyy
        # we don't use a SQL constraint. Include "self" in search in case we use create
        # multi with duplicated user / team pairs in it. Use an explicit active leaf
        # in domain as we may have an active_test in context that would break computation
        existing = self.env["work.team.member"].search(
            [
                ("work_team_id", "in", self.work_team_id.ids),
                ("user_id", "in", self.user_id.ids),
                ("active", "=", True),
            ]
        )
        duplicates = self.env["work.team.member"]
        active_records = dict(
            (membership.user_id.id, membership.work_team_id.id)
            for membership in self
            if membership.active
        )
        for membership in self:
            potential = existing.filtered(
                lambda m: m.user_id == membership.user_id
                and m.work_team_id == membership.work_team_id
                and m.id != membership.id
            )
            if not potential or len(potential) > 1:
                duplicates += potential
                continue
            if active_records.get(potential.user_id.id):
                duplicates += potential
            else:
                active_records[potential.user_id.id] = potential.work_team_id.id

        if duplicates:
            raise exceptions.ValidationError(
                _(
                    "You are trying to create duplicate membership(s). "
                    "We found that %(duplicates)s already exist(s).",
                    duplicates=", ".join(
                        "%s (%s)" % (m.user_id.name, m.work_team_id.name)
                        for m in duplicates
                    ),
                )
            )

    @api.depends_context("default_work_team_id")
    @api.depends("work_team_id", "user_id", "is_membership_multi")
    def _compute_user_in_teams_ids(self):
        """
        Give users not to add in the currently chosen team to avoid duplicates.
        In multi membership mode this field is empty as duplicates are allowed.
        """
        if all(m.is_membership_multi for m in self):
            member_user_ids = self.env["res.users"]
        elif self.ids:
            member_user_ids = (
                self.env["work.team.member"]
                .search([("id", "not in", self.ids)])
                .user_id
            )
        else:
            member_user_ids = self.env["work.team.member"].search([]).user_id
        for member in self:
            if member_user_ids:
                member.user_in_teams_ids = member_user_ids
            elif member.work_team_id:
                member.user_in_teams_ids = member.work_team_id.member_ids
            elif self.env.context.get("default_work_team_id"):
                member.user_in_teams_ids = (
                    self.env["work.team"]
                    .browse(self.env.context["default_work_team_id"])
                    .member_ids
                )
            else:
                member.user_in_teams_ids = self.env["res.users"]

    @api.depends("work_team_id")
    def _compute_user_company_ids(self):
        all_companies = self.env["res.company"].search([])
        for member in self:
            member.user_company_ids = member.work_team_id.company_id or all_companies

    @api.depends("work_team_id")
    def _compute_is_membership_multi(self):
        multi_enabled = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("work_team.membership_multi", False)
        )
        self.is_membership_multi = multi_enabled

    @api.depends("work_team_id", "user_id", "is_membership_multi", "active")
    def _compute_member_warning(self):
        """Display a warning message to warn user they are about to archive
        other memberships. Only valid in mono-membership mode and take into
        account only active memberships as we may keep several archived
        memberships."""
        if all(m.is_membership_multi for m in self):
            self.member_warning = False
        else:
            active = self.filtered("active")
            (self - active).member_warning = False
            if not active:
                return

            existing = self.env["work.team.member"].search(
                [("user_id", "in", active.user_id.ids)]
            )
            user_mapping = dict.fromkeys(existing.user_id, self.env["work.team"])
            for membership in existing:
                user_mapping[membership.user_id] |= membership.work_team_id

            for member in active:
                teams = user_mapping.get(member.user_id, self.env["work.team"])
                remaining = teams - (member.work_team_id | member._origin.work_team_id)
                if remaining:
                    member.member_warning = _(
                        "Adding %(user_name)s in this team will remove them from %(team_names)s. "
                        "Working in multiple teams? Activate the option under Configuration>Settings.",
                        user_name=member.user_id.name,
                        team_names=", ".join(remaining.mapped("name")),
                    )
                else:
                    member.member_warning = False

    # ------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------

    @api.model_create_multi
    def create(self, values_list):
        """Specific behavior implemented on create

          * mono membership mode: other user memberships are automatically
            archived (a warning already told it in form view);
          * creating a membership already existing as archived: do nothing as
            people can manage them from specific menu "Members";

        Also remove autofollow on create. No need to follow team members
        when creating them as chatter is mainly used for information purpose
        (tracked fields).
        """
        is_membership_multi = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("work_team.membership_multi", False)
        )
        if not is_membership_multi:
            self._synchronize_memberships(values_list)
        return super(
            CrmTeamMember, self.with_context(mail_create_nosubscribe=True)
        ).create(values_list)

    def write(self, values):
        """Specific behavior about active. If you change user_id / team_id user
        get warnings in form view and a raise in constraint check. We support
        archive / activation of memberships that toggles other memberships. But
        we do not support manual creation or update of user_id / team_id. This
        either works, either crashes). Indeed supporting it would lead to complex
        code with low added value. Users should create or remove members, and
        maybe archive / activate them. Updating manually memberships by
        modifying user_id or team_id is advanced and does not benefit from our
        support."""
        is_membership_multi = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("work_team.membership_multi", False)
        )
        if not is_membership_multi and values.get("active"):
            self._synchronize_memberships(
                [
                    dict(
                        user_id=membership.user_id.id,
                        work_team_id=membership.work_team_id.id,
                    )
                    for membership in self
                ]
            )
        return super(CrmTeamMember, self).write(values)

    def _synchronize_memberships(self, user_team_ids):
        """Synchronize memberships: archive other memberships.

        :param user_team_ids: list of pairs (user_id, work_team_id)
        """
        existing = self.search(
            [
                (
                    "active",
                    "=",
                    True,
                ),  # explicit search on active only, whatever context
                ("user_id", "in", [values["user_id"] for values in user_team_ids]),
            ]
        )
        user_memberships = dict.fromkeys(
            existing.user_id.ids, self.env["work.team.member"]
        )
        for membership in existing:
            user_memberships[membership.user_id.id] += membership

        existing_to_archive = self.env["work.team.member"]
        for values in user_team_ids:
            existing_to_archive += user_memberships.get(
                values["user_id"], self.env["work.team.member"]
            ).filtered(lambda m: m.work_team_id.id != values["work_team_id"])

        if existing_to_archive:
            existing_to_archive.action_archive()

        return existing_to_archive
