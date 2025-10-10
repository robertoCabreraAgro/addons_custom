from . import models
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Post-installation hook for base_approval_sales."""
    _logger.info("base_approval_sales: Post-installation hook executed successfully")
    # Simple hook - the module should work without complex migrations
    # The main functionality is in the models and views


def uninstall_hook(env):
    """Clean up when module is uninstalled."""
    _logger.info("base_approval_sales: Starting uninstallation cleanup...")

    try:
        # Reset orders in pending_approval state back to draft
        pending_orders = env['sale.order'].search([('state', '=', 'pending_approval')])
        if pending_orders:
            pending_orders.write({'state': 'draft'})
            _logger.info(f"Reset {len(pending_orders)} orders from pending_approval to draft")

        # Clear approval_request_ref fields to avoid orphaned references
        orders_with_refs = env['sale.order'].search([('approval_request_ref', '!=', False)])
        if orders_with_refs:
            orders_with_refs.write({'approval_request_ref': False})
            _logger.info(f"Cleared approval references from {len(orders_with_refs)} orders")

        _logger.info("base_approval_sales: Uninstallation cleanup completed successfully")

    except Exception as e:
        _logger.error(f"base_approval_sales: Uninstallation cleanup failed: {str(e)}", exc_info=True)