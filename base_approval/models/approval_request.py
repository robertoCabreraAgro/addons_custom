from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tools.translate import _


class ApprovalRequest(models.Model):
    _name = "approval.request"
    _description = "Approval Request"
    _inherit = ["mail.thread.main.attachment", "mail.activity.mixin"]
    _check_company_auto = True
    _mail_post_access = "read"
    _order = "name"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True,
    )
    category_id = fields.Many2one(
        comodel_name="approval.category",
        string="Category",
        required=True,
    )
    category_image = fields.Binary(related="category_id.image")
    request_owner_id = fields.Many2one(
        comodel_name="res.users",
        string="Request Owner",
        check_company=True,
        domain="[('company_ids', 'in', company_id)]",
        default=lambda self: self.env.user,
    )
    name = fields.Char(
        string="Approval Subject",
        tracking=True,
    )
    date = fields.Datetime(string="Date")
    date_start = fields.Datetime(string="Date start")
    date_end = fields.Datetime(string="Date end")
    date_deadline = fields.Datetime(string="Date Deadline")
    date_confirmed = fields.Datetime(string="Date Confirmed")
    location = fields.Char(string="Location")
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Contact",
        check_company=True,
    )
    reference = fields.Char(string="Reference")
    reason = fields.Html(string="Description")
    quantity = fields.Float(string="Quantity")
    amount = fields.Float(string="Amount")

    approver_ids = fields.One2many(
        comodel_name="approval.approver",
        inverse_name="request_id",
        string="Approvers",
        compute="_compute_approver_ids",
        store=True,
        readonly=False,
        check_company=True,
    )
    user_ids = fields.Many2many(
        comodel_name="res.users",
        string="Users",
        compute="_compute_user_ids",
        readonly=True,
    )
    state = fields.Selection(
        [
            ("new", "To Submit"),
            ("pending", "Submitted"),
            ("approved", "Approved"),
            ("refused", "Refused"),
            ("cancel", "Canceled"),
        ],
        default="new",
        # compute="_compute_state",
        # store=True,
        # tracking=True,
        # group_expand=True,
        # index=True,
    )
    request_status = fields.Selection(
        [
            ("new", "To Submit"),
            ("pending", "Submitted"),
            ("approved", "Approved"),
            ("refused", "Refused"),
            ("cancel", "Canceled"),
        ],
        default="new",
        compute="_compute_state",
        store=True,
        tracking=True,
        group_expand=True,
        index=True,
    )
    user_state = fields.Selection(
        [
            ("new", "New"),
            ("pending", "To Approve"),
            ("waiting", "Waiting"),
            ("approved", "Approved"),
            ("refused", "Refused"),
            ("cancel", "Canceled"),
        ],
        compute="_compute_user_state",
    )

    attachment_ids = fields.One2many(
        comodel_name="ir.attachment",
        inverse_name="res_id",
        domain=[("res_model", "=", "approval.request")],
        string="Attachments",
    )
    attachment_number = fields.Integer(
        string="Number of Attachments",
        compute="_compute_attachment_number",
    )

    product_line_ids = fields.One2many(
        comodel_name="approval.product.line",
        inverse_name="approval_request_id",
        check_company=True,
    )

    has_access_to_request = fields.Boolean(
        string="Has Access To Request",
        compute="_compute_has_access_to_request",
    )
    can_change_request_owner = fields.Boolean(
        string="Can Change Request Owner",
        compute="_compute_has_access_to_request",
    )

    has_date = fields.Selection(related="category_id.has_date")
    has_date_deadline = fields.Selection(related="category_id.has_date_deadline")
    has_period = fields.Selection(related="category_id.has_period")
    has_quantity = fields.Selection(related="category_id.has_quantity")
    has_amount = fields.Selection(related="category_id.has_amount")
    has_reference = fields.Selection(related="category_id.has_reference")
    has_partner = fields.Selection(related="category_id.has_partner")
    has_payment_method = fields.Selection(related="category_id.has_payment_method")
    has_location = fields.Selection(related="category_id.has_location")
    has_product = fields.Selection(related="category_id.has_product")
    requirer_document = fields.Selection(related="category_id.requirer_document")
    approval_minimum = fields.Integer(related="category_id.approval_minimum")
    approval_type = fields.Selection(related="category_id.approval_type")
    approve_sequentially = fields.Boolean(related="category_id.approve_sequentially")
    automated_sequence = fields.Boolean(related="category_id.automated_sequence")
    manager_approval = fields.Selection(related="category_id.manager_approval")

    # ------------------------------------------------------------
    # CONSTRAINTS
    # ------------------------------------------------------------

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for request in self:
            if (
                request.date_start
                and request.date_end
                and request.date_start > request.date_end
            ):
                raise ValidationError(_("Start date should precede the end date."))

    @api.constrains("approver_ids")
    def _check_approver_ids(self):
        for request in self:
            # make sure the approver_ids are unique per request
            if len(request.approver_ids) != len(request.approver_ids.user_id):
                raise UserError(
                    _(
                        "You cannot assign the same approver multiple times on the same request."
                    )
                )

    # ------------------------------------------------------------
    # CRUD METHODS
    # ------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            category = "category_id" in vals and self.env["approval.category"].browse(
                vals["category_id"]
            )
            if category and category.automated_sequence:
                vals["name"] = category.sequence_id.next_by_id()
        created_requests = super().create(vals_list)
        for request in created_requests:
            request.message_subscribe(
                partner_ids=request.request_owner_id.partner_id.ids
            )
        return created_requests

    def write(self, vals):
        if "request_owner_id" in vals:
            for approval in self:
                approval.message_unsubscribe(
                    partner_ids=approval.request_owner_id.partner_id.ids
                )

        res = super().write(vals)

        if "request_owner_id" in vals:
            for approval in self:
                approval.message_subscribe(
                    partner_ids=approval.request_owner_id.partner_id.ids
                )

        if "approver_ids" in vals:
            to_resequence = self.filtered_domain(
                [
                    ("approve_sequentially", "=", True),
                    ("state", "=", "pending"),
                ]
            )
            for approval in to_resequence:
                if not approval.approver_ids.filtered(lambda a: a.status == "pending"):
                    approver = approval.approver_ids.filtered(
                        lambda a: a.status == "waiting"
                    )
                    if approver:
                        approver[0].status = "pending"
                        approver[0]._create_activity()

        return res

    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        return [
            dict(vals, name=self.env._("%s (copy)", request.name))
            for request, vals in zip(self, vals_list)
        ]

    def unlink(self):
        self.filtered(lambda a: a.has_product).product_line_ids.unlink()
        return super().unlink()

    @api.ondelete(at_uninstall=False)
    def unlink_attachments(self):
        attachment_ids = self.env["ir.attachment"].search(
            [
                ("res_model", "=", "approval.request"),
                ("res_id", "in", self.ids),
            ]
        )
        if attachment_ids:
            attachment_ids.unlink()

    def _track_subtype(self, init_values):
        self.ensure_one()
        if "state" in init_values:
            return self.env.ref("base_approval.mt_approval_state")

        return super()._track_subtype(init_values)

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    def _compute_attachment_number(self):
        domain = [("res_model", "=", "approval.request"), ("res_id", "in", self.ids)]
        attachment_data = self.env["ir.attachment"]._read_group(
            domain, ["res_id"], ["__count"]
        )
        attachment = dict(attachment_data)
        for request in self:
            request.attachment_number = attachment.get(request.id, 0)

    @api.depends_context("uid")
    @api.depends("request_owner_id")
    def _compute_has_access_to_request(self):
        is_approval_user = self.env.user.has_group("base_approval.group_approval_user")
        self.can_change_request_owner = is_approval_user
        for request in self:
            request.has_access_to_request = (
                request.request_owner_id == self.env.user and is_approval_user
            )

    @api.depends("category_id", "request_owner_id")
    def _compute_approver_ids(self):
        for request in self:
            users_to_approver = {}
            for approver in request.approver_ids:
                users_to_approver[approver.user_id.id] = approver

            users_to_category_approver = {}
            for approver in request.category_id.approver_ids:
                users_to_category_approver[approver.user_id.id] = approver

            approver_id_vals = []

            if request.manager_approval:
                employee = self.env["hr.employee"].search(
                    [("user_id", "=", request.request_owner_id.id)], limit=1
                )
                if employee.parent_id.user_id:
                    manager_user_id = employee.parent_id.user_id.id
                    manager_required = (
                        request.manager_approval == "required"
                    )
                    # We set the manager sequence to be lower than all others (9) so they are the first to approve.
                    self._create_or_update_approver(
                        manager_user_id,
                        users_to_approver,
                        approver_id_vals,
                        manager_required,
                        9,
                    )
                    if manager_user_id in users_to_category_approver.keys():
                        users_to_category_approver.pop(manager_user_id)

            for user_id in users_to_category_approver:
                self._create_or_update_approver(
                    user_id,
                    users_to_approver,
                    approver_id_vals,
                    users_to_category_approver[user_id].required,
                    users_to_category_approver[user_id].sequence,
                )

            for current_approver in users_to_approver.values():
                # Reset sequence and required for the remaining approvers that are no (longer) part of the category approvers or managers.
                # Set the sequence of these manually added approvers to 1000, so that they always appear after the category approvers.
                self._update_approver_vals(
                    current_approver, approver_id_vals, False, 1000
                )

            request.update({"approver_ids": approver_id_vals})

    @api.depends("approver_ids")
    def _compute_user_ids(self):
        for request in self:
            request.user_ids = request.approver_ids.user_id

    @api.depends_context("uid")
    @api.depends("approver_ids.status")
    def _compute_user_state(self):
        for approval in self:
            approval.user_state = approval.approver_ids.filtered(
                lambda approver: approver.user_id == self.env.user
            ).status

    @api.depends("approver_ids.status", "approver_ids.required")
    def _compute_state(self):
        for request in self:
            status_lst = request.mapped("approver_ids.status")
            required_approved = all(
                a.status == "approved"
                for a in request.approver_ids.filtered("required")
            )
            minimal_approver = (
                request.approval_minimum
                if len(status_lst) >= request.approval_minimum
                else len(status_lst)
            )
            if status_lst:
                if status_lst.count("cancel"):
                    status = "cancel"
                elif status_lst.count("refused"):
                    status = "refused"
                elif status_lst.count("new"):
                    status = "new"
                elif (
                    status_lst.count("approved") >= minimal_approver
                    and required_approved
                ):
                    status = "approved"
                else:
                    status = "pending"
            else:
                status = "new"
            request.state = status

        self.filtered_domain(
            [("state", "in", ["approved", "refused", "cancel"])]
        )._cancel_activities()

    # ------------------------------------------------------------
    # ACTION METHODS
    # ------------------------------------------------------------

    def action_get_attachment_view(self):
        self.ensure_one()
        res = self.env["ir.actions.act_window"]._for_xml_id("base.action_attachment")
        res["domain"] = [
            ("res_model", "=", "approval.request"),
            ("res_id", "in", self.ids),
        ]
        res["context"] = {
            "default_res_model": "approval.request",
            "default_res_id": self.id,
        }
        return res

    def action_confirm(self):
        self.ensure_one()
        self._check_manager_approval_constraints()
        self._check_enough_approvers()
        self._check_requirer_document_has_attachment()
        approvers = self.approver_ids
        if self.approve_sequentially:
            approvers = approvers.filtered(
                lambda a: a.status in ["new", "pending", "waiting"]
            )
            approvers[1:].sudo().write({"status": "waiting"})
            approvers = (
                approvers[0]
                if approvers and approvers[0].status != "pending"
                else self.env["approval.approver"]
            )
        else:
            approvers = approvers.filtered(lambda a: a.status == "new")
        approvers._create_activity()
        approvers.sudo().write({"status": "pending"})
        self.sudo().write({"date_confirmed": fields.Datetime.now()})

    def action_approve(self, approver=None):
        self._check_approve_sequentially_can_approve()
        if not isinstance(approver, models.BaseModel):
            approver = self.mapped("approver_ids").filtered(
                lambda approver: approver.user_id == self.env.user
            )
        approver.write({"status": "approved"})
        # Send approval accepted message
        for approval in self:
            if approval.request_owner_id.partner_id:
                body = _(
                    "The request created on %(create_date)s by %(request_owner)s has been accepted.",
                    create_date=approval.create_date.date(),
                    request_owner=approval.request_owner_id.name,
                )
                subject = _(
                    "The request %(request_name)s for %(request_owner)s has been accepted",
                    request_name=approval.name,
                    request_owner=approval.request_owner_id.name,
                )
                approval.message_notify(
                    body=body,
                    subject=subject,
                    partner_ids=approval.request_owner_id.partner_id.ids,
                )
        self.sudo()._update_next_approvers_status(
            approver,
            "pending",
            only_next_approver=True,
        )
        self.sudo()._get_user_approval_activities(user=self.env.user).action_feedback()

    def action_refuse(self, approver=None):
        if not isinstance(approver, models.BaseModel):
            approver = self.mapped("approver_ids").filtered(
                lambda approver: approver.user_id == self.env.user
            )
        approver.write({"status": "refused"})
        # Send approval refused message
        for approval in self:
            if approval.request_owner_id.partner_id:
                body = _(
                    "The request created on %(create_date)s by %(request_owner)s has been refused.",
                    create_date=approval.create_date.date(),
                    request_owner=approval.request_owner_id.name,
                )
                subject = _(
                    "The request %(request_name)s for %(request_owner)s has been refused",
                    request_name=approval.name,
                    request_owner=approval.request_owner_id.name,
                )
                approval.message_notify(
                    body=body,
                    subject=subject,
                    partner_ids=approval.request_owner_id.partner_id.ids,
                )
        self.sudo()._update_next_approvers_status(
            approver, "refused", only_next_approver=False, cancel_activities=True
        )
        self.sudo()._get_user_approval_activities(user=self.env.user).action_feedback()

    def action_withdraw(self, approver=None):
        if not isinstance(approver, models.BaseModel):
            approver = self.mapped("approver_ids").filtered(
                lambda approver: approver.user_id == self.env.user
            )
        self.sudo()._update_next_approvers_status(
            approver, "waiting", only_next_approver=False, cancel_activities=True
        )
        approver.write({"status": "pending"})

    def action_draft(self):
        self.mapped("approver_ids").write({"status": "new"})

    def action_cancel(self):
        self.sudo()._get_user_approval_activities(user=self.env.user).unlink()
        self.mapped("approver_ids").write({"status": "cancel"})

    # ------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------

    def _cancel_activities(self):
        approval_activity = self.env.ref("base_approval.mail_activity_data_approval")
        activities = self.activity_ids.filtered(
            lambda a: a.activity_type_id == approval_activity
        )
        activities.unlink()

    @api.model
    def _create_or_update_approver(
        self, user_id, users_to_approver, approver_id_vals, required, sequence
    ):
        if user_id not in users_to_approver.keys():
            approver_id_vals.append(
                Command.create(
                    {
                        "user_id": user_id,
                        "status": "new",
                        "required": required,
                        "sequence": sequence,
                    }
                )
            )
        else:
            current_approver = users_to_approver.pop(user_id)
            self._update_approver_vals(
                current_approver, approver_id_vals, required, sequence
            )

    @api.model
    def _update_approver_vals(
        self, approver, approver_id_vals, new_required, new_sequence
    ):
        if approver.required != new_required or approver.sequence != new_sequence:
            approver_id_vals.append(
                Command.update(
                    approver.id, {"required": new_required, "sequence": new_sequence}
                )
            )

    def _update_next_approvers_status(
        self, approver, new_status, only_next_approver, cancel_activities=False
    ):
        approvers_updated = self.env["approval.approver"]
        for approval in self.filtered("approve_sequentially"):
            current_approver = approval.approver_ids & approver
            approvers_to_update = approval.approver_ids.filtered(
                lambda a: a.status not in ["approved", "refused"]
                and (
                    a.sequence > current_approver.sequence
                    or (
                        a.sequence == current_approver.sequence
                        and a.id > current_approver.id
                    )
                )
            )
            if only_next_approver and approvers_to_update:
                approvers_to_update = approvers_to_update[0]
            approvers_updated |= approvers_to_update
        approvers_updated.sudo().status = new_status
        if new_status == "pending":
            approvers_updated._create_activity()
        if cancel_activities:
            approvers_updated.request_id._cancel_activities()

    def _get_user_approval_activities(self, user):
        domain = [
            ("res_model", "=", "approval.request"),
            ("res_id", "in", self.ids),
            (
                "activity_type_id",
                "=",
                self.env.ref("base_approval.mail_activity_data_approval").id,
            ),
            ("user_id", "=", user.id),
        ]
        activities = self.env["mail.activity"].search(domain)
        return activities

    # ------------------------------------------------------------
    # VALIDATIONS
    # ------------------------------------------------------------

    def _check_enough_approvers(self):
        if len(self.approver_ids) < self.approval_minimum:
            raise UserError(
                _(
                    "You have to add at least %s approvers to confirm your request.",
                    self.approval_minimum,
                )
            )

    def _check_requirer_document_has_attachment(self):
        if self.requirer_document == "required" and not self.attachment_number:
            raise UserError(_("You have to attach at least one document."))

    def _check_manager_approval_constraints(self):
        if self.manager_approval == "required":
            employee = self.env["hr.employee"].search(
                [
                    ("user_id", "=", self.request_owner_id.id),
                    ("company_id", "=", self.company_id.id),
                ],
                limit=1,
            )

            if not employee.parent_id:
                raise UserError(
                    _(
                        "This request needs to be approved by your manager. There is no manager "
                        "linked to your employee profile."
                    )
                )

            if not employee.parent_id.user_id:
                raise UserError(
                    _(
                        "This request needs to be approved by your manager. There is no user "
                        "linked to your manager."
                    )
                )

            if not self.approver_ids.filtered(
                lambda a: a.user_id.id == employee.parent_id.user_id.id
            ):
                raise UserError(
                    _(
                        "This request needs to be approved by your manager. "
                        "Your manager is not in the approvers list."
                    )
                )

    def _check_approve_sequentially_can_approve(self):
        if self.approve_sequentially and self.user_state == "waiting":
            raise ValidationError(_("You cannot approve before the previous approver."))
