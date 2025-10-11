from . import models
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Post-installation hook for base_approval_sales."""
    _logger.info("base_approval_sales: Starting post-installation hook...")

    try:
        # Ensure the approval category exists and is properly configured
        _ensure_approval_category_exists(env)

        # Verify basic configuration
        _verify_installation(env)

        _logger.info("base_approval_sales: Post-installation hook executed successfully")

    except Exception as e:
        _logger.error("base_approval_sales: Post-installation hook failed: %s", str(e), exc_info=True)


def _ensure_approval_category_exists(env):
    """Ensure the Sales Order Approval category exists with all required fields."""
    try:
        # Check if category already exists
        existing_category = env['approval.category'].search([
            ('name', '=', 'Sales Order Approval')
        ], limit=1)

        if existing_category:
            _logger.info("Approval category already exists (ID: %s)", existing_category.id)
            # Verify it has all required fields
            _verify_category_fields(existing_category)
            return existing_category

        # Create the category with all required fields
        _logger.info("Creating new approval category...")
        category_vals = _get_complete_category_values(env)

        # Create category with sudo() to bypass permissions
        category = env['approval.category'].sudo().create(category_vals)
        _logger.info("Created approval category with ID: %s", category.id)

        # Create default approvers
        _create_default_approvers(env, category)

        return category

    except Exception as e:
        _logger.error("Failed to ensure approval category exists: %s", str(e), exc_info=True)
        return None


def _get_complete_category_values(env):
    """Get complete category values with ALL required fields."""
    # Get the first company or current company
    company = env.company or env['res.company'].search([], limit=1)

    category_vals = {
        "name": "Sales Order Approval",
        "company_id": company.id,
        "active": True,
        "description": "Categoría de aprobación para todas las órdenes de venta",

        # CORE REQUIRED FIELDS - Features we need for sales orders
        "has_amount": "required",
        "has_partner": "required",
        "has_reference": "required",

        # ALL OTHER REQUIRED FIELDS - Set to "no" (not needed for sales orders)
        "has_date": "no",
        "has_date_deadline": "no",
        "has_date_planned": "no",
        "has_date_range": "no",
        "has_payment_method": "no",
        "has_product": "no",
        "has_quantity": "no",
        "has_location": "no",
        "has_document": "optional",

        # APPROVAL CONFIGURATION
        "approval_minimum": 1,
        "approve_sequentially": False,
        "manager_approval": "required",

        # SEQUENCE CONFIGURATION
        "automated_sequence": True,
        "sequence_code": "SO-APPR-",
    }

    # Add extended fields if they exist (from inheriting modules)
    extended_fields = {
        "has_bsl": "no",  # from telegram_bot module
        "has_operation_type": "no",  # from telegram_bot module
        "has_journal": "no",  # from marin module
        "has_vehicle": "no",  # from marin module
        "has_odometer": "no",  # from marin module
    }

    # Only add fields that exist in the model
    approval_category_model = env['approval.category']
    for field_name, value in extended_fields.items():
        if hasattr(approval_category_model, field_name):
            category_vals[field_name] = value
            _logger.debug("Added extended field %s = %s", field_name, value)

    return category_vals


def _create_default_approvers(env, category):
    """Create default approvers for the category."""
    try:
        # Find sales managers
        try:
            sales_managers = env.ref("sales_team.group_sale_manager").users
        except ValueError:
            try:
                # Fallback to admin user
                admin_user = env.ref("base.user_admin")
                sales_managers = admin_user
            except ValueError:
                _logger.error("Cannot find admin user for approver creation")
                return

        if not sales_managers:
            _logger.warning("No sales managers found for approver creation")
            return

        # Ensure it's a recordset
        if not hasattr(sales_managers, 'ids'):
            sales_managers = env['res.users'].browse([sales_managers.id])

        # Create approvers
        approvers_created = 0
        for i, manager in enumerate(sales_managers[:3]):  # Max 3 approvers
            try:
                approver_vals = {
                    "category_id": category.id,
                    "user_id": manager.id,
                    "required": i == 0,  # First one is required
                    "sequence": (i + 1) * 10,
                }
                env["approval.category.approver"].sudo().create(approver_vals)
                approvers_created += 1
                _logger.info("Created approver %s for category %s", manager.name, category.id)
            except Exception as e:
                _logger.warning("Failed to create approver %s: %s", manager.name, str(e))

        if approvers_created == 0:
            _logger.warning("No approvers created for category %s", category.id)
        else:
            _logger.info("Created %s approvers for category %s", approvers_created, category.id)

    except Exception as e:
        _logger.error("Failed to create default approvers: %s", str(e), exc_info=True)


def _verify_category_fields(category):
    """Verify that the category has all required fields properly set."""
    required_fields = [
        'has_amount', 'has_partner', 'has_reference', 'has_date', 'has_date_deadline',
        'has_date_planned', 'has_date_range', 'has_payment_method', 'has_product',
        'has_quantity', 'has_location', 'has_document'
    ]

    missing_fields = []
    for field in required_fields:
        if not hasattr(category, field) or not getattr(category, field):
            missing_fields.append(field)

    if missing_fields:
        _logger.warning("Category %s is missing required fields: %s", category.id, missing_fields)
    else:
        _logger.info("Category %s has all required fields", category.id)


def _verify_installation(env):
    """Verify basic installation requirements."""
    try:
        # Check if approval.category model exists
        if 'approval.category' not in env:
            _logger.error("approval.category model not found - base_approval module missing?")
            return False

        # Check if sale.order model exists
        if 'sale.order' not in env:
            _logger.error("sale.order model not found - sale module missing?")
            return False

        _logger.info("Basic installation verification passed")
        return True

    except Exception as e:
        _logger.error("Installation verification failed: %s", str(e))
        return False


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