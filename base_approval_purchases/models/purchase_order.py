from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class PurchaseOrder(models.Model):
    """Extend purchase order with optional approval integration."""
    _inherit = "purchase.order"

    # ============================================================================
    # FIELDS
    # ============================================================================

    # Optional approval integration fields
    approval_request_purchase_id = fields.Many2one(
        "approval.request.purchase",
        string="Purchase Approval Request",
        copy=False,
        readonly=True,
        help="Purchase approval request associated with this order"
    )

    approval_status = fields.Selection(
        related="approval_request_purchase_id.state",
        string="Approval Status",
        store=True,
        readonly=True
    )

    require_approval = fields.Boolean(
        string="Requires Approval",
        compute="_compute_require_approval",
        help="Whether this purchase order requires approval"
    )

    is_editable = fields.Boolean(
        string="Is Editable",
        compute="_compute_is_editable",
        help="Whether this purchase order can be edited"
    )

    # ============================================================================
    # COMPUTE METHODS
    # ============================================================================

    @api.depends("company_id", "amount_total")
    def _compute_require_approval(self):
        """Compute if purchase order requires approval based on company settings."""
        for order in self:
            # Check if purchase approval is enabled for the company
            requires_approval = order.company_id.purchase_approval_limit > 0

            # Check if amount exceeds the approval limit
            if requires_approval and order.amount_total > order.company_id.purchase_approval_limit:
                order.require_approval = True
            else:
                order.require_approval = False

    @api.depends("state", "approval_request_purchase_id", "approval_status")
    def _compute_is_editable(self):
        """Compute if purchase order is editable."""
        for order in self:
            if order.state in ("draft", "sent"):
                # If has approval request, check approval status
                if order.approval_request_purchase_id:
                    order.is_editable = order.approval_status in ("draft", "to_approve")
                else:
                    order.is_editable = True
            else:
                order.is_editable = False

    # ============================================================================
    # ACTION METHODS
    # ============================================================================

    def action_create_approval_request(self):
        """Create an approval request for this purchase order."""
        self.ensure_one()

        if self.approval_request_purchase_id:
            raise UserError(_("Approval request already exists for this purchase order."))

        if not self.require_approval:
            raise UserError(_("This purchase order does not require approval."))

        # Get default approval category
        category = self._get_approval_category()
        if not category:
            raise UserError(_("No approval category configured for purchase orders."))

        # Create approval request
        vals = self._prepare_approval_request_vals(category)
        approval_request = self.env["approval.request.purchase"].create(vals)

        # Create product lines
        self._create_approval_product_lines(approval_request)

        # Link approval request to purchase order
        self.approval_request_purchase_id = approval_request.id

        # Return action to view the approval request
        return approval_request.get_formview_action()

    def action_view_approval_request(self):
        """View the associated approval request."""
        self.ensure_one()

        if not self.approval_request_purchase_id:
            raise UserError(_("No approval request associated with this purchase order."))

        return self.approval_request_purchase_id.get_formview_action()

    def button_confirm(self):
        """Override confirmation to check approval status."""
        for order in self:
            # Check if approval is required and completed
            if order.require_approval:
                if not order.approval_request_purchase_id:
                    # Create approval request automatically
                    order.action_create_approval_request()
                    raise UserError(
                        _("This purchase order requires approval. "
                          "An approval request has been created. "
                          "Please complete the approval process before confirming.")
                    )
                elif order.approval_status != "approved":
                    raise UserError(
                        _("This purchase order cannot be confirmed until the approval request is approved.")
                    )

        # Proceed with normal confirmation
        return super().button_confirm()

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def _get_approval_category(self):
        """Get the appropriate approval category for this purchase order."""
        # Try to find category based on amount
        categories = self.env["approval.category.purchase"].search([
            ("company_id", "=", self.company_id.id),
            ("active", "=", True),
            "|",
            ("minimum_amount", "<=", self.amount_total),
            ("minimum_amount", "=", 0),
            "|",
            ("maximum_amount", ">=", self.amount_total),
            ("maximum_amount", "=", 0)
        ], limit=1)

        if categories:
            return categories[0]

        # Fallback to default category
        return self.company_id.default_approval_category_id

    def _prepare_approval_request_vals(self, category):
        """Prepare values for creating approval request."""
        return {
            "category_purchase_id": category.id,
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
            "requested_by": self.env.user.id,
            "purchase_order_id": self.id,
        }

    def _create_approval_product_lines(self, approval_request):
        """Create product lines for the approval request."""
        for line in self.order_line:
            vals = {
                "approval_request_purchase_id": approval_request.id,
                "sequence": line.sequence,
                "display_type": line.display_type,
                "product_id": line.product_id.id if line.product_id else False,
                "name": line.name,
                "product_qty": line.product_qty,
                "product_uom": line.product_uom.id if line.product_uom else False,
                "price_unit": line.price_unit,
                "discount": getattr(line, "discount", 0.0),
                "taxes_id": [(6, 0, line.taxes_id.ids)],
                "date_planned": line.date_planned,
                "analytic_distribution": getattr(line, "analytic_distribution", {}),
                "purchase_line_id": line.id,
            }
            self.env["approval.purchase.product.line"].create(vals)

    def sync_from_approval_request(self):
        """Sync data from approval request back to purchase order."""
        if not self.approval_request_purchase_id:
            return

        approval = self.approval_request_purchase_id

        # Update header fields
        update_vals = {
            "partner_id": approval.partner_id.id,
            "partner_ref": approval.partner_ref,
            "date_order": approval.date_order,
            "date_planned": approval.date_planned,
            "payment_term_id": approval.payment_term_id.id,
            "fiscal_position_id": approval.fiscal_position_id.id,
            "incoterm_id": approval.incoterm_id.id,
            "dest_address_id": approval.dest_address_id.id,
            "picking_type_id": approval.picking_type_id.id,
            "notes": approval.notes,
            "user_id": approval.user_id.id,
        }

        self.write(update_vals)

        # Sync product lines
        self._sync_lines_from_approval(approval)

    def _sync_lines_from_approval(self, approval):
        """Sync product lines from approval request."""
        # This would implement bidirectional sync logic
        # For now, just update basic quantities
        for approval_line in approval.product_line_ids:
            if approval_line.purchase_line_id:
                purchase_line = approval_line.purchase_line_id
                purchase_line.write({
                    "product_qty": approval_line.product_qty,
                    "price_unit": approval_line.price_unit,
                    "date_planned": approval_line.date_planned,
                })

    # ============================================================================
    # HOOKS FOR EXTENSIBILITY
    # ============================================================================

    @api.model
    def _get_approval_required_conditions(self):
        """Hook to define custom approval requirements.

        Override this method to add custom logic for determining
        when approval is required.

        Returns:
            dict: Conditions for requiring approval
        """
        return {
            "amount_threshold": True,
            "vendor_restrictions": False,
            "product_restrictions": False,
            "department_restrictions": False,
        }

    def _hook_before_approval_creation(self):
        """Hook called before creating approval request.

        Override this method to add custom validation or
        preparation logic before approval creation.
        """
        pass

    def _hook_after_approval_creation(self, approval_request):
        """Hook called after creating approval request.

        Args:
            approval_request: The created approval request

        Override this method to add custom logic after
        approval request creation.
        """
        pass

    def _hook_on_approval_complete(self):
        """Hook called when approval is completed.

        Override this method to add custom logic when
        approval process is completed.
        """
        pass