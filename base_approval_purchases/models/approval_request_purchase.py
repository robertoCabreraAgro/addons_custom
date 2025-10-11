from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class ApprovalRequestPurchase(models.Model):
    """Purchase Order approval request model."""
    _name = "approval.request.purchase"
    _description = "Purchase Order Approval Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"
    _check_company_auto = True

    # ============================================================================
    # FIELDS
    # ============================================================================

    # Basic Information
    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _("New"),
        tracking=True
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        index=True,
        default=lambda self: self.env.company
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    # Purchase Information
    partner_id = fields.Many2one(
        "res.partner",
        string="Vendor",
        required=True,
        domain="[('supplier_rank', '>', 0)]",
        tracking=True
    )

    partner_ref = fields.Char(
        string="Vendor Reference",
        copy=False,
        help="Reference of the sales order or bid sent by the vendor."
    )

    # Dates
    date_order = fields.Datetime(
        string="Order Date",
        required=True,
        default=fields.Datetime.now,
        tracking=True
    )

    date_planned = fields.Datetime(
        string="Expected Date",
        required=True,
        default=fields.Datetime.now,
        tracking=True,
        help="Delivery date expected by vendor."
    )

    # Amounts
    amount_untaxed = fields.Monetary(
        string="Untaxed Amount",
        store=True,
        readonly=True,
        compute="_compute_amount_all",
        currency_field="currency_id"
    )

    amount_tax = fields.Monetary(
        string="Taxes",
        store=True,
        readonly=True,
        compute="_compute_amount_all",
        currency_field="currency_id"
    )

    amount_total = fields.Monetary(
        string="Total",
        store=True,
        readonly=True,
        compute="_compute_amount_all",
        currency_field="currency_id",
        tracking=True
    )

    # Approval Related
    category_purchase_id = fields.Many2one(
        "approval.category.purchase",
        string="Approval Category",
        required=True,
        tracking=True
    )

    state = fields.Selection([
        ("draft", "Draft"),
        ("to_approve", "To Approve"),
        ("approved", "Approved"),
        ("refused", "Refused"),
        ("cancelled", "Cancelled")
    ], string="Status", default="draft", tracking=True, index=True)

    approval_status = fields.Selection([
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("refused", "Refused")
    ], string="Approval Status", default="pending", tracking=True)

    # Relations
    purchase_order_id = fields.Many2one(
        "purchase.order",
        string="Purchase Order",
        copy=False,
        readonly=True
    )

    approval_request_id = fields.Many2one(
        "approval.request",
        string="Generic Approval Request",
        copy=False,
        readonly=True,
        help="Link to generic approval request if using base approval"
    )

    # Product Lines
    product_line_ids = fields.One2many(
        "approval.purchase.product.line",
        "approval_request_purchase_id",
        string="Products",
        copy=True
    )

    # User and Security
    requested_by = fields.Many2one(
        "res.users",
        string="Requested by",
        required=True,
        default=lambda self: self.env.user,
        tracking=True
    )

    user_id = fields.Many2one(
        "res.users",
        string="Responsible",
        default=lambda self: self.env.user,
        tracking=True
    )

    # Approval Configuration
    require_validation = fields.Boolean(
        string="Requires Validation",
        related="category_purchase_id.require_validation",
        readonly=True
    )

    approver_ids = fields.One2many(
        "approval.request.purchase.approver",
        "request_id",
        string="Approvers"
    )

    current_approver_id = fields.Many2one(
        "res.users",
        string="Current Approver",
        compute="_compute_current_approver",
        store=True
    )

    next_approver_id = fields.Many2one(
        "res.users",
        string="Next Approver",
        compute="_compute_next_approver",
        store=True
    )

    # Computed Fields
    is_editable = fields.Boolean(
        string="Is Editable",
        compute="_compute_is_editable"
    )

    can_approve = fields.Boolean(
        string="Can Approve",
        compute="_compute_can_approve"
    )

    purchase_order_count = fields.Integer(
        string="Purchase Orders",
        compute="_compute_purchase_order_count"
    )

    approval_count = fields.Integer(
        string="Approvals",
        compute="_compute_approval_count"
    )

    # Additional Purchase Fields
    payment_term_id = fields.Many2one(
        "account.payment.term",
        string="Payment Terms"
    )

    fiscal_position_id = fields.Many2one(
        "account.fiscal.position",
        string="Fiscal Position"
    )

    incoterm_id = fields.Many2one(
        "account.incoterms",
        string="Incoterm"
    )

    dest_address_id = fields.Many2one(
        "res.partner",
        string="Dropship Address"
    )

    picking_type_id = fields.Many2one(
        "stock.picking.type",
        string="Deliver To"
    )

    # Notes
    notes = fields.Html(
        string="Terms and Conditions"
    )

    # Confirmation
    date_confirmed = fields.Datetime(
        string="Confirmation Date",
        readonly=True,
        copy=False
    )

    # Approval History
    approval_history_ids = fields.One2many(
        "approval.request.purchase.history",
        "request_id",
        string="Approval History"
    )

    # ============================================================================
    # CRUD METHODS
    # ============================================================================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "approval.request.purchase"
                ) or _("New")
        return super().create(vals_list)

    # ============================================================================
    # COMPUTE METHODS
    # ============================================================================

    @api.depends("product_line_ids.price_total")
    def _compute_amount_all(self):
        for request in self:
            amount_untaxed = amount_tax = 0.0
            for line in request.product_line_ids:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            request.update({
                "amount_untaxed": amount_untaxed,
                "amount_tax": amount_tax,
                "amount_total": amount_untaxed + amount_tax,
            })

    @api.depends("approver_ids", "approver_ids.status", "state")
    def _compute_current_approver(self):
        for request in self:
            if request.state == "to_approve":
                current = request.approver_ids.filtered(
                    lambda a: a.status == "pending"
                )
                request.current_approver_id = current[0].user_id if current else False
            else:
                request.current_approver_id = False

    @api.depends("approver_ids", "approver_ids.status", "approver_ids.sequence")
    def _compute_next_approver(self):
        for request in self:
            if request.state == "to_approve":
                pending = request.approver_ids.filtered(
                    lambda a: a.status == "pending"
                ).sorted("sequence")
                request.next_approver_id = pending[0].user_id if pending else False
            else:
                request.next_approver_id = False

    @api.depends("state", "requested_by")
    def _compute_is_editable(self):
        for request in self:
            request.is_editable = (
                request.state in ("draft", "to_approve") and
                (request.requested_by == self.env.user or
                 self.env.user.has_group("base_approval_purchases.group_purchase_manager"))
            )

    @api.depends("current_approver_id", "state")
    def _compute_can_approve(self):
        for request in self:
            request.can_approve = (
                request.state == "to_approve" and
                request.current_approver_id == self.env.user
            )

    def _compute_purchase_order_count(self):
        for request in self:
            request.purchase_order_count = 1 if request.purchase_order_id else 0

    def _compute_approval_count(self):
        for request in self:
            request.approval_count = len(request.approver_ids)

    # ============================================================================
    # ACTION METHODS
    # ============================================================================

    def action_submit(self):
        """Submit the request for approval."""
        self.ensure_one()
        if not self.product_line_ids:
            raise ValidationError(_("Cannot submit request without products."))

        # Setup approval flow based on category
        self._setup_approval_flow()
        self.write({
            "state": "to_approve",
            "date_confirmed": fields.Datetime.now()
        })

        # Send notifications
        self._send_approval_notifications()

    def action_approve(self):
        """Approve the request."""
        self.ensure_one()
        if not self.can_approve:
            raise ValidationError(_("You are not authorized to approve this request."))

        # Update current approver
        current_approver = self.approver_ids.filtered(
            lambda a: a.user_id == self.env.user and a.status == "pending"
        )
        if current_approver:
            current_approver.write({
                "status": "approved",
                "approved_date": fields.Datetime.now()
            })

            # Log approval
            self._log_approval_action("approved")

            # Check if all approvals are complete
            self._check_approval_completion()

    def action_refuse(self):
        """Refuse the request."""
        self.ensure_one()
        if not self.can_approve:
            raise ValidationError(_("You are not authorized to refuse this request."))

        # Update current approver
        current_approver = self.approver_ids.filtered(
            lambda a: a.user_id == self.env.user and a.status == "pending"
        )
        if current_approver:
            current_approver.write({
                "status": "refused",
                "approved_date": fields.Datetime.now()
            })

            # Log refusal
            self._log_approval_action("refused")

            # Set request as refused
            self.write({
                "state": "refused",
                "approval_status": "refused"
            })

    def action_cancel(self):
        """Cancel the request."""
        self.ensure_one()
        self.write({"state": "cancelled"})

    def action_draft(self):
        """Reset to draft."""
        self.ensure_one()
        self.approver_ids.write({"status": "pending"})
        self.write({"state": "draft"})

    def action_create_po(self):
        """Create purchase order from approval request."""
        self.ensure_one()
        if self.state != "approved":
            raise ValidationError(_("Only approved requests can create purchase orders."))

        if self.purchase_order_id:
            raise ValidationError(_("Purchase order already exists."))

        # Create purchase order
        po_vals = self._prepare_purchase_order_vals()
        purchase_order = self.env["purchase.order"].create(po_vals)

        # Create purchase order lines
        for line in self.product_line_ids:
            line_vals = line._prepare_purchase_order_line_vals(purchase_order.id)
            self.env["purchase.order.line"].create(line_vals)

        self.purchase_order_id = purchase_order.id
        return self.action_view_purchase_order()

    def action_view_purchase_order(self):
        """View the related purchase order."""
        self.ensure_one()
        if not self.purchase_order_id:
            return

        return {
            "name": _("Purchase Order"),
            "type": "ir.actions.act_window",
            "res_model": "purchase.order",
            "view_mode": "form",
            "res_id": self.purchase_order_id.id,
            "target": "current",
        }

    def action_view_approvals(self):
        """View approvers."""
        self.ensure_one()
        return {
            "name": _("Approvals"),
            "type": "ir.actions.act_window",
            "res_model": "approval.request.purchase.approver",
            "view_mode": "tree,form",
            "domain": [("request_id", "=", self.id)],
            "context": {"default_request_id": self.id},
        }

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def _setup_approval_flow(self):
        """Setup the approval flow based on category configuration."""
        self.ensure_one()
        if not self.category_purchase_id:
            return

        # Clear existing approvers
        self.approver_ids.unlink()

        # Get required approvers from category
        approvers = self.category_purchase_id.get_required_approvers(self)

        # Create approver records
        for sequence, approver_data in enumerate(approvers, 1):
            self.env["approval.request.purchase.approver"].create({
                "request_id": self.id,
                "user_id": approver_data.get("user_id"),
                "sequence": sequence,
                "role": approver_data.get("role", "approver"),
                "status": "pending",
                "required": approver_data.get("required", True)
            })

    def _check_approval_completion(self):
        """Check if all required approvals are complete."""
        self.ensure_one()
        if not self.category_purchase_id:
            return

        # Check approval completion based on category rules
        if self.category_purchase_id.is_approval_complete(self):
            self.write({
                "state": "approved",
                "approval_status": "approved"
            })
            # Send approval notification
            self._send_approval_complete_notification()

    def _log_approval_action(self, action):
        """Log approval action in history."""
        self.env["approval.request.purchase.history"].create({
            "request_id": self.id,
            "user_id": self.env.user.id,
            "action": action,
            "date": fields.Datetime.now(),
            "comment": f"Request {action} by {self.env.user.name}"
        })

    def _send_approval_notifications(self):
        """Send notifications when request is submitted."""
        # Implementation for notifications
        pass

    def _send_approval_complete_notification(self):
        """Send notification when approval is complete."""
        # Implementation for completion notifications
        pass

    def _prepare_purchase_order_vals(self):
        """Prepare values for purchase order creation."""
        return {
            "partner_id": self.partner_id.id,
            "partner_ref": self.partner_ref,
            "date_order": self.date_order,
            "date_planned": self.date_planned,
            "currency_id": self.currency_id.id,
            "payment_term_id": self.payment_term_id.id,
            "fiscal_position_id": self.fiscal_position_id.id,
            "incoterm_id": self.incoterm_id.id,
            "dest_address_id": self.dest_address_id.id,
            "picking_type_id": self.picking_type_id.id,
            "notes": self.notes,
            "company_id": self.company_id.id,
            "user_id": self.user_id.id,
        }