"""
Complete Integration Tests for base_approval_sales

This module tests the complete centralized approval workflow,
ensuring it's the ONLY source of truth for sales order approvals.
"""

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install', 'approval_integration')
class TestCompleteApprovalIntegration(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Test data
        cls.partner = cls.env.ref('base.res_partner_1')
        cls.product = cls.env.ref('product.product_product_1')
        cls.company = cls.env.company

        # Create test users
        cls.salesperson = cls.env['res.users'].create({
            'name': 'Test Salesperson',
            'login': 'test_sales',
            'email': 'test_sales@example.com',
            'groups_id': [(6, 0, [cls.env.ref('sales_team.group_sale_salesman').id])],
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
        })

        cls.sales_manager = cls.env['res.users'].create({
            'name': 'Test Sales Manager',
            'login': 'test_manager',
            'email': 'test_manager@example.com',
            'groups_id': [(6, 0, [cls.env.ref('sales_team.group_sale_manager').id])],
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
        })

        # Ensure approval category exists
        cls.approval_category = cls.env['approval.category'].search([
            ('name', '=', 'Sales Order Approval'),
            ('company_id', '=', cls.company.id),
        ], limit=1)

        if not cls.approval_category:
            cls.approval_category = cls.env['approval.category'].create({
                'name': 'Sales Order Approval',
                'company_id': cls.company.id,
                'has_amount': 'required',
                'has_partner': 'required',
                'has_reference': 'required',
                'approval_minimum': 1,
                'automated_sequence': True,
                'sequence_code': 'SO-APPR-TEST-',
            })

            # Add manager as approver
            cls.env['approval.category.approver'].create({
                'category_id': cls.approval_category.id,
                'user_id': cls.sales_manager.id,
                'required': True,
                'sequence': 10,
            })

    def test_01_centralized_logic_active(self):
        """Test that our centralized approval logic is active and working."""
        # Test with salesperson user
        order = self.env['sale.order'].with_user(self.salesperson).create({
            'partner_id': self.partner.id,
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })

        # Verify our centralized logic is working
        self.assertTrue(order.require_approval, "All orders should require approval")
        self.assertTrue(order.approval_request_id, "Approval request should be created automatically")
        self.assertEqual(order.approval_state, 'new', "Initial approval state should be 'new'")
        self.assertEqual(order.approval_state_display, 'Sin Solicitar', "Display should be in Spanish")

    def test_02_complete_approval_workflow(self):
        """Test the complete approval workflow from creation to confirmation."""
        # Step 1: Create order (as salesperson)
        order = self.env['sale.order'].with_user(self.salesperson).create({
            'partner_id': self.partner.id,
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 2,
                'price_unit': 150.0,
            })],
        })

        self.assertEqual(order.state, 'draft')
        self.assertTrue(order.approval_request_id)
        self.assertEqual(order.approval_state, 'new')

        # Step 2: Cannot confirm without approval
        with self.assertRaises(UserError) as ctx:
            order.action_confirm()
        self.assertIn('requiere aprobación', str(ctx.exception))

        # Step 3: Request approval
        result = order.action_request_approval()
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(order.state, 'pending_approval')
        self.assertEqual(order.approval_state, 'pending')
        self.assertEqual(order.approval_state_display, 'En Espera de Aprobación')

        # Step 4: Salesperson cannot approve
        self.assertFalse(order.with_user(self.salesperson).can_approve)
        self.assertFalse(order.with_user(self.salesperson).can_reject)

        # Step 5: Manager can approve
        order_as_manager = order.with_user(self.sales_manager)
        self.assertTrue(order_as_manager.can_approve)
        self.assertTrue(order_as_manager.can_reject)

        # Step 6: Approve
        result = order_as_manager.action_approve()
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(order.approval_state, 'approved')
        self.assertEqual(order.approval_state_display, 'Aprobado')
        self.assertEqual(order.state, 'draft')  # Ready for confirmation

        # Step 7: Now can confirm
        order.action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_03_rejection_workflow(self):
        """Test approval rejection workflow."""
        order = self.env['sale.order'].with_user(self.salesperson).create({
            'partner_id': self.partner.id,
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 50.0,
            })],
        })

        # Request approval
        order.action_request_approval()
        self.assertEqual(order.state, 'pending_approval')

        # Manager rejects
        result = order.with_user(self.sales_manager).action_reject()
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(order.approval_state, 'refused')
        self.assertEqual(order.approval_state_display, 'Rechazado')
        self.assertEqual(order.state, 'cancel')

    def test_04_state_transitions_spanish(self):
        """Test that all state transitions show proper Spanish labels."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })

        # Test state selection includes our pending_approval state
        state_field = order._fields['state']
        state_selection = dict(state_field.get_description(self.env)['selection'])

        self.assertIn('pending_approval', state_selection)
        self.assertEqual(state_selection['pending_approval'], 'En Espera de Aprobación')

        # Test approval state display translations
        test_states = {
            'new': 'Sin Solicitar',
            'pending': 'En Espera de Aprobación',
            'approved': 'Aprobado',
            'refused': 'Rechazado',
            'cancel': 'Cancelado',
        }

        for state, expected_display in test_states.items():
            # Mock the approval state
            order.approval_request_id = self.env['approval.request'].create({
                'name': 'Test Request',
                'category_id': self.approval_category.id,
                'request_owner_id': self.env.user.id,
            })
            order.approval_request_id.write({'state': state})
            order._compute_approval_state_display()
            self.assertEqual(order.approval_state_display, expected_display)

    def test_05_external_approval_logic_disabled(self):
        """Test that external approval logic is disabled/overridden."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })

        # Test that _approval_allowed uses our logic
        self.assertFalse(order._approval_allowed(), "Should require approval")

        # Mock approved state
        order.approval_request_id = self.env['approval.request'].create({
            'name': 'Test Request',
            'category_id': self.approval_category.id,
            'request_owner_id': self.env.user.id,
            'state': 'approved',
        })
        self.assertTrue(order._approval_allowed(), "Should allow when approved")

        # Test that _compute_approval_state does nothing (overridden)
        original_state = order.approval_state
        order._compute_approval_state()
        self.assertEqual(order.approval_state, original_state, "Should not change via compute")

    def test_06_automatic_approval_request_creation(self):
        """Test that approval requests are created automatically."""
        # Test on create
        order1 = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })
        self.assertTrue(order1.approval_request_id, "Should create approval request on create")

        # Test on write (adding order lines)
        order2 = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })
        order2.approval_request_id.unlink()  # Remove to test recreation

        order2.write({
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })
        self.assertTrue(order2.approval_request_id, "Should recreate approval request on write")

    def test_07_approval_permissions_computation(self):
        """Test that approval permissions are computed correctly."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })

        order.action_request_approval()

        # Test with different users
        order_as_salesperson = order.with_user(self.salesperson)
        self.assertFalse(order_as_salesperson.can_approve)
        self.assertFalse(order_as_salesperson.can_reject)

        order_as_manager = order.with_user(self.sales_manager)
        self.assertTrue(order_as_manager.can_approve)
        self.assertTrue(order_as_manager.can_reject)

        # Test after approval
        order_as_manager.action_approve()
        self.assertFalse(order_as_manager.can_approve)  # Can't approve twice
        self.assertFalse(order_as_manager.can_reject)   # Can't reject approved

    def test_08_onchange_warnings(self):
        """Test that onchange warnings work correctly."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })

        # Remove approval request to test warning
        order.approval_request_id.unlink()

        # Trigger onchange
        result = order._onchange_approval_warning()
        self.assertIn('warning', result)
        self.assertIn('Aprobación Requerida', result['warning']['title'])

    def test_09_approval_summary_api(self):
        """Test the get_approval_summary API method."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })

        # Test initial state
        summary = order.get_approval_summary()
        self.assertEqual(summary['status'], 'not_requested')

        # Test after requesting approval
        order.action_request_approval()
        summary = order.get_approval_summary()
        self.assertEqual(summary['status'], 'pending')
        self.assertIn('approvers', summary)
        self.assertIn('url', summary)

    def test_10_error_handling(self):
        """Test error handling in various scenarios."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })

        # Test requesting approval twice
        order.action_request_approval()
        with self.assertRaises(UserError) as ctx:
            order.action_request_approval()
        self.assertIn('pendiente', str(ctx.exception))

        # Test approving without permissions
        with self.assertRaises(UserError) as ctx:
            order.with_user(self.salesperson).action_approve()
        self.assertIn('permisos', str(ctx.exception))

        # Test viewing approval request when none exists
        order_without_approval = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })
        order_without_approval.approval_request_id.unlink()

        with self.assertRaises(UserError) as ctx:
            order_without_approval.action_view_approval_request()
        self.assertIn('No hay solicitud', str(ctx.exception))

    def test_11_migration_data_consistency(self):
        """Test that migration maintains data consistency."""
        # This would typically be tested with demo data or by creating
        # orders in the old format and running the migration hook

        orders = self.env['sale.order'].search([
            ('state', 'in', ['draft', 'sent']),
            ('require_approval', '=', True),
        ])

        for order in orders:
            # All orders requiring approval should have approval requests
            if order.require_approval:
                self.assertTrue(order.approval_request_id,
                               f"Order {order.name} requires approval but has no request")

            # States should be consistent
            if order.approval_request_id and order.approval_request_id.state == 'pending':
                self.assertEqual(order.state, 'pending_approval',
                               f"Order {order.name} has pending approval but wrong state")

    def test_12_ui_integration(self):
        """Test UI-related functionality."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })

        # Test that all required fields for UI are available
        required_fields = [
            'require_approval', 'approval_state', 'approval_state_display',
            'can_approve', 'can_reject', 'approval_request_id'
        ]

        for field_name in required_fields:
            self.assertTrue(hasattr(order, field_name),
                           f"Field {field_name} should exist for UI")

        # Test action results are properly formatted
        result = order.action_request_approval()
        self.assertIn('type', result)
        self.assertIn('tag', result)
        self.assertIn('params', result)


@tagged('post_install', '-at_install', 'approval_performance')
class TestApprovalPerformance(TransactionCase):
    """Test performance aspects of the approval system."""

    def test_bulk_order_creation(self):
        """Test performance with bulk order creation."""
        partner = self.env.ref('base.res_partner_1')

        # Create multiple orders to test performance
        order_count = 50
        orders_data = []

        for i in range(order_count):
            orders_data.append({
                'partner_id': partner.id,
                'name': f'TEST-{i:03d}',
            })

        # Measure time for bulk creation
        import time
        start_time = time.time()

        orders = self.env['sale.order'].create(orders_data)

        end_time = time.time()
        creation_time = end_time - start_time

        # Verify all orders have approval requests
        orders_with_approval = orders.filtered('approval_request_id')
        self.assertEqual(len(orders_with_approval), order_count,
                        "All orders should have approval requests")

        # Performance should be reasonable (less than 1 second per 10 orders)
        max_expected_time = order_count / 10
        self.assertLess(creation_time, max_expected_time,
                       f"Creation took {creation_time:.2f}s, expected < {max_expected_time:.2f}s")

        _logger.info(f"Created {order_count} orders with approvals in {creation_time:.2f}s")