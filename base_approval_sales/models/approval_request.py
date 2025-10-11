import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ApprovalRequest(models.Model):
    """Extend approval request for sales order integration with auto-update."""
    _inherit = "approval.request"

    # Link to sale order if this request is for a sale order
    sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Sale Order",
        help="Related sale order for this approval request",
    )

    @api.model
    def create(self, vals):
        """Override create to link sale order if reference matches.

        This method automatically establishes the link between approval requests
        and sale orders when they are created, using the reference field to match
        the sale order name.
        """
        request = super().create(vals)

        # Try to link with sale order using multiple strategies
        sale_order = self._find_and_link_sale_order(request)
        if sale_order:
            request.sale_order_id = sale_order.id
            _logger.debug("Linked approval request %s to sale order %s", request.name, sale_order.name)

        return request

    def _find_and_link_sale_order(self, request):
        """Find and link a sale order to this approval request.

        Args:
            request: The approval request record

        Returns:
            sale.order: The found sale order or empty recordset
        """
        # Method 1: Search by reference field matching sale order name
        if request.reference:
            sale_order = self.env["sale.order"].search([
                ("name", "=", request.reference)
            ], limit=1)
            if sale_order:
                return sale_order

        # Method 2: Check if there's a sale order with this approval request already
        sale_order = self.env["sale.order"].search([
            ("approval_request_id", "=", request.id)
        ], limit=1)
        if sale_order:
            return sale_order

        # No sale order found
        return self.env["sale.order"]

    def action_approve(self, approver=None):
        """Override action_approve to auto-update linked sale orders.

        This method extends the base approval functionality to automatically
        update the state of linked sale orders when approval requests are approved.
        It maintains the original approval logic while adding sale order integration.
        """
        # Call the parent method to maintain original approval behavior
        result = super().action_approve(approver)

        # Update linked sale orders when approval is completed
        self._update_linked_sale_orders_on_approval()

        # Return reload action if called from UI to refresh the view
        if self.env.context.get('from_ui'):
            return {'type': 'ir.actions.client', 'tag': 'reload'}

        return result

    def action_refuse(self, approver=None):
        """Override action_refuse to auto-update linked sale orders.

        This method extends the base refusal functionality to automatically
        update the state of linked sale orders when approval requests are refused.
        """
        # Call the parent method to maintain original refusal behavior
        result = super().action_refuse(approver)

        # Update linked sale orders when approval is refused
        self._update_linked_sale_orders_on_refusal()

        # Return reload action if called from UI to refresh the view
        if self.env.context.get('from_ui'):
            return {'type': 'ir.actions.client', 'tag': 'reload'}

        return result

    def _update_linked_sale_orders_on_approval(self):
        """Update linked sale orders when approval request is approved.

        This method finds and updates sale orders that are linked to this
        approval request, setting their state to 'approved' when the
        approval request reaches 'approved' state.
        """
        for request in self:
            # Only process requests that are now approved
            if request.state != 'approved':
                continue

            try:
                # Find linked sale order through multiple methods
                sale_order = self._find_linked_sale_order(request)

                if sale_order:
                    # Update sale order state to approved
                    sale_order.state = 'approved'

                    # Invalidate cache to ensure UI updates
                    sale_order.invalidate_recordset(['state', 'approval_state_display'])

                    _logger.info("Updated sale order %s to 'approved' state after approval request %s was approved",
                               sale_order.name, request.name)
                else:
                    _logger.debug("No linked sale order found for approval request %s", request.name)

            except Exception as e:
                _logger.error("Error updating sale order state for approval request %s: %s",
                            request.name, str(e), exc_info=True)

    def _update_linked_sale_orders_on_refusal(self):
        """Update linked sale orders when approval request is refused.

        This method finds and updates sale orders that are linked to this
        approval request, setting their state back to 'draft' when the
        approval request is refused.
        """
        for request in self:
            # Only process requests that are now refused
            if request.state != 'refused':
                continue

            try:
                # Find linked sale order through multiple methods
                sale_order = self._find_linked_sale_order(request)

                if sale_order:
                    # Update sale order state back to draft for modification
                    sale_order.state = 'draft'

                    # Invalidate cache to ensure UI updates
                    sale_order.invalidate_recordset(['state', 'approval_state_display'])

                    _logger.info("Updated sale order %s to 'draft' state after approval request %s was refused",
                               sale_order.name, request.name)
                else:
                    _logger.debug("No linked sale order found for approval request %s", request.name)

            except Exception as e:
                _logger.error("Error updating sale order state for approval request %s: %s",
                            request.name, str(e), exc_info=True)

    def _find_linked_sale_order(self, request):
        """Find the sale order linked to this approval request.

        This method uses multiple strategies to find the linked sale order:
        1. Direct link through sale_order_id field
        2. Search by reference field matching sale order name
        3. Search through approval_request_id field in sale orders

        Args:
            request: The approval request record

        Returns:
            sale.order: The linked sale order or empty recordset
        """
        # Method 1: Direct link through sale_order_id field
        if request.sale_order_id:
            return request.sale_order_id

        # Method 2: Search by reference field matching sale order name
        if request.reference:
            sale_order = self.env["sale.order"].search([
                ("name", "=", request.reference)
            ], limit=1)
            if sale_order:
                return sale_order

        # Method 3: Search through approval_request_id field in sale orders
        sale_order = self.env["sale.order"].search([
            ("approval_request_id", "=", request.id)
        ], limit=1)
        if sale_order:
            return sale_order

        # No linked sale order found
        return self.env["sale.order"]