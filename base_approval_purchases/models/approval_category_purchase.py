from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class ApprovalCategoryPurchase(models.Model):
    """Approval categories specific for purchase orders."""
    _name = "approval.category.purchase"
    _description = "Purchase Approval Category"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"

    # ============================================================================
    # FIELDS
    # ============================================================================

    # Basic Information
    name = fields.Char(
        string="Category Name",
        required=True,
        tracking=True
    )

    code = fields.Char(
        string="Code",
        required=True,
        copy=False
    )

    sequence = fields.Integer(
        string="Sequence",
        default=10
    )

    active = fields.Boolean(
        string="Active",
        default=True,
        tracking=True
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id
    )

    description = fields.Text(
        string="Description"
    )

    # Amount Limits
    minimum_amount = fields.Monetary(
        string="Minimum Amount",
        default=0.0,
        help="Minimum amount for this approval category"
    )

    maximum_amount = fields.Monetary(
        string="Maximum Amount",
        help="Maximum amount for this approval category. Leave empty for no limit."
    )

    auto_approve_below = fields.Monetary(
        string="Auto Approve Below",
        default=0.0,
        help="Orders below this amount are automatically approved"
    )

    # Approval Configuration
    approval_type = fields.Selection([
        ("simple", "Simple Approval"),
        ("sequential", "Sequential Approval"),
        ("parallel", "Parallel Approval")
    ], string="Approval Type", default="simple", required=True)

    approval_minimum = fields.Integer(
        string="Minimum Approvals",
        default=1,
        help="Minimum number of approvals required"
    )

    approval_sequence = fields.Boolean(
        string="Sequential Approval",
        help="Approvers must approve in sequence"
    )

    escalation_days = fields.Integer(
        string="Escalation Days",
        default=0,
        help="Days before escalating to next approver. 0 = no escalation"
    )

    # Manager Approval
    manager_approval = fields.Selection([
        ("no", "No Manager Approval"),
        ("optional", "Optional Manager Approval"),
        ("required", "Required Manager Approval")
    ], string="Manager Approval", default="no")

    require_manager_first = fields.Boolean(
        string="Manager Must Approve First",
        help="Manager must approve before other approvers"
    )

    # Validation Rules
    require_rfq_validation = fields.Boolean(
        string="Require RFQ Validation",
        help="Require validation that quotes were requested from multiple vendors"
    )

    require_budget_check = fields.Boolean(
        string="Require Budget Check",
        help="Require validation against budget availability"
    )

    require_invoice_match = fields.Boolean(
        string="Require Invoice Matching",
        help="Require three-way matching (PO, Receipt, Invoice)"
    )

    require_validation = fields.Boolean(
        string="Requires Validation",
        compute="_compute_require_validation",
        store=True
    )

    # Product and Partner Restrictions
    allowed_product_categ_ids = fields.Many2many(
        "product.category",
        "approval_category_product_categ_rel",
        "category_id", "product_categ_id",
        string="Allowed Product Categories",
        help="Only products from these categories can be approved"
    )

    allowed_partner_ids = fields.Many2many(
        "res.partner",
        "approval_category_partner_rel",
        "category_id", "partner_id",
        string="Allowed Vendors",
        domain="[('supplier_rank', '>', 0)]",
        help="Only these vendors can be used for orders in this category"
    )

    forbidden_partner_ids = fields.Many2many(
        "res.partner",
        "approval_category_forbidden_partner_rel",
        "category_id", "partner_id",
        string="Forbidden Vendors",
        domain="[('supplier_rank', '>', 0)]",
        help="These vendors cannot be used for orders in this category"
    )

    # Approvers
    approver_ids = fields.Many2many(
        "res.users",
        "approval_category_purchase_approver_rel",
        "category_id", "user_id",
        string="Approvers",
        domain="[('share', '=', False)]"
    )

    # Automation
    create_po_on_approval = fields.Boolean(
        string="Create PO on Approval",
        help="Automatically create purchase order when approved"
    )

    auto_send_po = fields.Boolean(
        string="Auto Send PO",
        help="Automatically send purchase order to vendor"
    )

    po_approval_method = fields.Selection([
        ("manual", "Manual Approval"),
        ("auto", "Auto Approval"),
        ("amount_based", "Amount Based")
    ], string="PO Approval Method", default="manual")

    # Notifications
    notify_on_approval = fields.Boolean(
        string="Notify on Approval",
        default=True
    )

    notify_on_refusal = fields.Boolean(
        string="Notify on Refusal",
        default=True
    )

    email_template_id = fields.Many2one(
        "mail.template",
        string="Email Template",
        domain="[('model_id.model', '=', 'approval.request.purchase')]"
    )

    notification_config = fields.Text(
        string="Notification Configuration",
        help="JSON configuration for notifications"
    )

    # Statistics
    total_requests = fields.Integer(
        string="Total Requests",
        compute="_compute_request_statistics"
    )

    approved_requests = fields.Integer(
        string="Approved Requests",
        compute="_compute_request_statistics"
    )

    refused_requests = fields.Integer(
        string="Refused Requests",
        compute="_compute_request_statistics"
    )

    pending_requests = fields.Integer(
        string="Pending Requests",
        compute="_compute_request_statistics"
    )

    total_amount_approved = fields.Monetary(
        string="Total Amount Approved",
        compute="_compute_amount_statistics"
    )

    avg_approval_time = fields.Float(
        string="Average Approval Time (Days)",
        compute="_compute_time_statistics"
    )

    last_request_date = fields.Datetime(
        string="Last Request Date",
        compute="_compute_time_statistics"
    )

    request_count = fields.Integer(
        string="Request Count",
        compute="_compute_request_count"
    )

    # ============================================================================
    # COMPUTE METHODS
    # ============================================================================

    @api.depends("approval_minimum", "manager_approval", "require_rfq_validation",
                 "require_budget_check", "require_invoice_match")
    def _compute_require_validation(self):
        for category in self:
            category.require_validation = any([
                category.approval_minimum > 0,
                category.manager_approval != "no",
                category.require_rfq_validation,
                category.require_budget_check,
                category.require_invoice_match
            ])

    def _compute_request_statistics(self):
        domain_base = [("category_purchase_id", "in", self.ids)]

        total_data = self.env["approval.request.purchase"]._read_group(
            domain_base, ["category_purchase_id"], ["__count"]
        )
        total_mapping = {data[0]: data[1] for data in total_data}

        approved_data = self.env["approval.request.purchase"]._read_group(
            domain_base + [("state", "=", "approved")],
            ["category_purchase_id"], ["__count"]
        )
        approved_mapping = {data[0]: data[1] for data in approved_data}

        refused_data = self.env["approval.request.purchase"]._read_group(
            domain_base + [("state", "=", "refused")],
            ["category_purchase_id"], ["__count"]
        )
        refused_mapping = {data[0]: data[1] for data in refused_data}

        pending_data = self.env["approval.request.purchase"]._read_group(
            domain_base + [("state", "=", "to_approve")],
            ["category_purchase_id"], ["__count"]
        )
        pending_mapping = {data[0]: data[1] for data in pending_data}

        for category in self:
            category.total_requests = total_mapping.get(category.id, 0)
            category.approved_requests = approved_mapping.get(category.id, 0)
            category.refused_requests = refused_mapping.get(category.id, 0)
            category.pending_requests = pending_mapping.get(category.id, 0)

    def _compute_amount_statistics(self):
        domain = [
            ("category_purchase_id", "in", self.ids),
            ("state", "=", "approved")
        ]
        amount_data = self.env["approval.request.purchase"]._read_group(
            domain, ["category_purchase_id"], ["amount_total:sum"]
        )
        amount_mapping = {data[0]: data[1] for data in amount_data}

        for category in self:
            category.total_amount_approved = amount_mapping.get(category.id, 0.0)

    def _compute_time_statistics(self):
        for category in self:
            requests = self.env["approval.request.purchase"].search([
                ("category_purchase_id", "=", category.id),
                ("state", "=", "approved"),
                ("date_confirmed", "!=", False)
            ])

            if requests:
                # Calculate average approval time
                approval_times = []
                for request in requests:
                    if request.date_confirmed:
                        delta = request.date_confirmed - request.create_date
                        approval_times.append(delta.total_seconds() / 86400)  # Convert to days

                category.avg_approval_time = sum(approval_times) / len(approval_times) if approval_times else 0.0
                category.last_request_date = max(requests.mapped("create_date"))
            else:
                category.avg_approval_time = 0.0
                category.last_request_date = False

    def _compute_request_count(self):
        request_data = self.env["approval.request.purchase"]._read_group(
            [("category_purchase_id", "in", self.ids)],
            ["category_purchase_id"], ["__count"]
        )
        request_mapping = {data[0]: data[1] for data in request_data}

        for category in self:
            category.request_count = request_mapping.get(category.id, 0)

    # ============================================================================
    # CONSTRAINTS
    # ============================================================================

    @api.constrains("minimum_amount", "maximum_amount")
    def _check_amount_limits(self):
        for category in self:
            if (category.maximum_amount and category.minimum_amount and
                category.minimum_amount > category.maximum_amount):
                raise ValidationError(
                    _("Minimum amount cannot be greater than maximum amount.")
                )

    @api.constrains("auto_approve_below", "minimum_amount")
    def _check_auto_approve_amount(self):
        for category in self:
            if (category.auto_approve_below and category.minimum_amount and
                category.auto_approve_below < category.minimum_amount):
                raise ValidationError(
                    _("Auto approve amount cannot be less than minimum amount.")
                )

    @api.constrains("code")
    def _check_unique_code(self):
        for category in self:
            domain = [
                ("code", "=", category.code),
                ("company_id", "=", category.company_id.id),
                ("id", "!=", category.id)
            ]
            if self.search_count(domain) > 0:
                raise ValidationError(
                    _("Code must be unique per company.")
                )

    # ============================================================================
    # ACTION METHODS
    # ============================================================================

    def action_view_requests(self):
        """View approval requests for this category."""
        self.ensure_one()
        return {
            "name": _("Approval Requests"),
            "type": "ir.actions.act_window",
            "res_model": "approval.request.purchase",
            "view_mode": "tree,form",
            "domain": [("category_purchase_id", "=", self.id)],
            "context": {"default_category_purchase_id": self.id},
        }

    # ============================================================================
    # BUSINESS METHODS
    # ============================================================================

    def get_required_approvers(self, request):
        """Get list of required approvers for this category and request."""
        self.ensure_one()
        approvers = []

        # Add manager if required
        if self.manager_approval in ("required", "optional"):
            manager = self._get_manager_approver(request)
            if manager:
                approvers.append({
                    "user_id": manager.id,
                    "role": "manager",
                    "required": self.manager_approval == "required"
                })

        # Add category approvers
        for user in self.approver_ids:
            if user not in [a.get("user_id") for a in approvers]:
                approvers.append({
                    "user_id": user.id,
                    "role": "approver",
                    "required": True
                })

        return approvers

    def is_approval_complete(self, request):
        """Check if approval is complete for the request."""
        self.ensure_one()

        if self.approval_type == "simple":
            return self._check_simple_approval(request)
        elif self.approval_type == "sequential":
            return self._check_sequential_approval(request)
        elif self.approval_type == "parallel":
            return self._check_parallel_approval(request)

        return False

    def check_amount_limits(self, amount):
        """Check if amount falls within category limits."""
        self.ensure_one()

        if self.minimum_amount and amount < self.minimum_amount:
            return False, _("Amount below minimum limit of %s") % self.minimum_amount

        if self.maximum_amount and amount > self.maximum_amount:
            return False, _("Amount exceeds maximum limit of %s") % self.maximum_amount

        return True, _("Amount within limits")

    def check_auto_approval(self, amount):
        """Check if amount qualifies for auto approval."""
        self.ensure_one()

        if not self.auto_approve_below:
            return False, _("Auto approval not configured")

        if amount <= self.auto_approve_below:
            return True, _("Qualifies for auto approval")

        return False, _("Amount exceeds auto approval limit")

    def validate_products(self, product_lines):
        """Validate that all products are allowed in this category."""
        self.ensure_one()

        if not self.allowed_product_categ_ids:
            return True, _("No product restrictions")

        errors = []
        for line in product_lines:
            if line.product_id and line.product_id.categ_id not in self.allowed_product_categ_ids:
                errors.append(_("Product '%s' category is not allowed") % line.product_id.name)

        if errors:
            return False, "; ".join(errors)

        return True, _("All products are valid")

    def validate_partner(self, partner):
        """Validate that the partner is allowed for this category."""
        self.ensure_one()

        if not partner:
            return False, _("No vendor selected")

        # Check forbidden partners
        if self.forbidden_partner_ids and partner in self.forbidden_partner_ids:
            return False, _("Vendor '%s' is forbidden") % partner.name

        # Check allowed partners
        if self.allowed_partner_ids and partner not in self.allowed_partner_ids:
            return False, _("Vendor '%s' is not in allowed list") % partner.name

        return True, _("Vendor is valid")

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def _get_manager_approver(self, request):
        """Get the manager approver for the request."""
        if not request.requested_by:
            return False

        employee = self.env["hr.employee"].search([
            ("user_id", "=", request.requested_by.id)
        ], limit=1)

        return employee.parent_id.user_id if employee.parent_id else False

    def _check_simple_approval(self, request):
        """Check simple approval completion."""
        approved_count = len(request.approver_ids.filtered(lambda a: a.status == "approved"))
        return approved_count >= self.approval_minimum

    def _check_sequential_approval(self, request):
        """Check sequential approval completion."""
        required_approvers = request.approver_ids.filtered("required").sorted("sequence")
        for approver in required_approvers:
            if approver.status != "approved":
                return False
        return True

    def _check_parallel_approval(self, request):
        """Check parallel approval completion."""
        approved_count = len(request.approver_ids.filtered(lambda a: a.status == "approved"))
        required_count = len(request.approver_ids.filtered("required"))
        return approved_count >= min(self.approval_minimum, required_count)