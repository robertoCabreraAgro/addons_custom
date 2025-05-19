from odoo import models, fields, api


class ApprovalApprover(models.Model):
    _name = "approval.approver"
    _description = "Approver"
    _order = "sequence, id"
    _check_company_auto = True

    request_id = fields.Many2one(
        comodel_name="approval.request",
        string="Request",
        check_company=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        related="request_id.company_id",
        string="Company",
        store=True,
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
    )
    status = fields.Selection(
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

    @api.depends("request_id.request_owner_id", "request_id.approver_ids.user_id")
    def _compute_existing_request_user_ids(self):
        for approver in self:
            approver.existing_request_user_ids = (
                self.mapped("request_id.approver_ids.user_id")._origin
                | self.request_id.request_owner_id._origin
            )

    @api.depends("user_id", "category_approver")
    def _compute_category_approver(self):
        for approval in self:
            approval.category_approver = (
                approval.user_id in approval.request_id.category_id.approver_ids.user_id
            )

    @api.depends_context("uid")
    @api.depends("user_id", "category_approver")
    def _compute_can_edit(self):
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

    def action_approve(self):
        self.request_id.action_approve(self)

    def action_refuse(self):
        self.request_id.action_refuse(self)

    def _create_activity(self):
        for approver in self:
            approver.request_id.activity_schedule(
                "base_approval.mail_activity_data_approval", user_id=approver.user_id.id
            )
