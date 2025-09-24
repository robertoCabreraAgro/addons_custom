from odoo import models, fields, api


class ApprovalApprover(models.Model):
    """
    Approval Approver Model.

    This model represents individual approvers for an approval request.
    It manages the state of each approver's decision, supports sequential
    and parallel approval workflows, and tracks whether approvers are
    required or optional.

    The model ensures data consistency across companies and prevents
    duplicate approvers in the same request through computed domains.
    """

    _name = "approval.approver"
    _description = "Approver"
    _order = "sequence, id"
    _check_company_auto = True

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    request_id = fields.Many2one(
        comodel_name="approval.request",
        string="Request",
        check_company=True,
        ondelete="cascade",
        index=True,  # Index for joining with approval requests
    )
    company_id = fields.Many2one(
        related="request_id.company_id",
        store=True,
        string="Company",
        readonly=True,
        index=True,
    )
    existing_request_user_ids = fields.Many2many(
        comodel_name="res.users",
        compute="_compute_existing_request_user_ids",
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="User",
        required=True,
        check_company=True,
        domain="['|', ('id', 'not in', existing_request_user_ids), ('id', '=', user_id)]",
        index=True,  # Index for filtering approvals by user
    )
    state = fields.Selection(
        [
            ("new", "New"),
            ("pending", "To Approve"),
            ("waiting", "Waiting"),
            ("approved", "Approved"),
            ("refused", "Refused"),
            ("cancel", "Cancel"),
        ],
        string="Status",
        default="new",
        readonly=True,
        index=True,  # Index for filtering by approval state
    )
    sequence = fields.Integer("Sequence", default=10)
    required = fields.Boolean(default=False, readonly=True)
    category_approver = fields.Boolean(
        compute="_compute_category_approver",
    )
    can_edit = fields.Boolean(
        compute="_compute_can_edit",
    )
    can_edit_user_id = fields.Boolean(
        compute="_compute_can_edit",
        help="Simple users should not be able to remove themselves as approvers "
        "because they will lose access to the record if they misclick.",
    )

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    @api.depends("request_id.request_owner_id", "request_id.approver_ids.user_id")
    def _compute_existing_request_user_ids(self):
        """
        Compute list of users already assigned to this request.

        This method creates a domain to prevent duplicate approver assignments
        by tracking all users who are already approvers or the request owner.
        The computed field is used to dynamically filter available users in the
        user selection field.

        :return: None (sets existing_request_user_ids field)
        """
        for approver in self:
            approver.existing_request_user_ids = (
                self.mapped("request_id.approver_ids.user_id")._origin
                | self.request_id.request_owner_id._origin
            )

    @api.depends("user_id", "category_approver")
    def _compute_category_approver(self):
        """
        Determine if the approver is defined at the category level.

        Category approvers are pre-defined in the approval category configuration
        and cannot be removed from individual requests. This ensures that mandatory
        approvers defined in the category are always included.

        :return: None (sets category_approver field)
        """
        for approval in self:
            approval.category_approver = (
                approval.user_id in approval.request_id.category_id.approver_ids.user_id
            )

    @api.depends_context("uid")
    @api.depends("user_id", "category_approver")
    def _compute_can_edit(self):
        """
        Compute edit permissions for the approver record.

        This method determines whether the current user can modify the approver
        assignment based on their permissions and relationship to the request.

        Rules:
        - can_edit: True if user is not set, not a category approver, or user has approval rights
        - can_edit_user_id: Prevents users from removing themselves to avoid losing access

        :return: None (sets can_edit and can_edit_user_id fields)
        """
        is_user = self.env.user.has_group("base_approval.group_approval_user")
        for approval in self:
            approval.can_edit = (
                not approval.user_id or not approval.category_approver or is_user
            )
            approval.can_edit_user_id = (
                is_user
                or approval.request_id.request_owner_id == self.env.user
                or not approval.user_id
            )

    # ------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------

    def action_approve(self):
        """
        Approve the request from this approver's perspective.

        This method delegates to the parent request's approval logic,
        passing the current approver record to identify who is approving.
        The actual approval logic and state transitions are handled by
        the approval.request model.

        :return: Result of request_id.action_approve()
        :raises ValidationError: If approval conditions are not met
        """
        self.request_id.action_approve(self)

    def action_refuse(self):
        """
        Refuse the request from this approver's perspective.

        This method delegates to the parent request's refusal logic,
        passing the current approver record to identify who is refusing.
        When any approver refuses, the entire request is typically refused.

        :return: Result of request_id.action_refuse()
        :raises ValidationError: If refusal conditions are not met
        """
        self.request_id.action_refuse(self)

    # ------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------

    def _create_activity(self):
        """
        Create mail activities for approvers to review the request.

        This method schedules a mail.activity for each approver, creating
        a task in their activity list to review and approve/refuse the request.
        Activities are automatically marked as done when the approver takes action.

        The activity type is defined by the 'mail_activity_data_approval' XML record
        which specifies the activity summary, icon, and default delay.

        :return: None
        """
        for approver in self:
            approver.request_id.activity_schedule(
                "base_approval.mail_activity_data_approval", user_id=approver.user_id.id
            )
