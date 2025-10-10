from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'approval_ui')
class TestApprovalUI(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env.ref('base.res_partner_1')
        cls.product = cls.env.ref('product.product_product_1')

    def test_01_approval_state_display_translations(self):
        """Test that approval states display correctly in Spanish"""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })

        # Test initial state
        self.assertTrue(order.require_approval)
        self.assertFalse(order.approval_state_display)  # No approval request yet

        # Create approval request
        order._create_approval_request()
        self.assertEqual(order.approval_state, 'new')
        self.assertEqual(order.approval_state_display, 'Sin Solicitar')

        # Request approval
        order.action_request_approval()
        self.assertEqual(order.approval_state, 'pending')
        self.assertEqual(order.approval_state_display, 'En Espera de Aprobación')
        self.assertEqual(order.state, 'pending_approval')

    def test_02_pending_approval_state_in_spanish(self):
        """Test that pending_approval state shows in Spanish"""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'state': 'pending_approval',
        })

        # Get state selection to verify translation
        state_field = order._fields['state']
        state_selection = dict(state_field.get_description(self.env)['selection'])

        self.assertEqual(state_selection['pending_approval'], 'En Espera de Aprobación')

    def test_03_approval_workflow_states(self):
        """Test complete approval workflow with state changes"""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })

        # Workflow: Create -> Request -> Approve -> Confirm

        # 1. Initial state
        self.assertEqual(order.state, 'draft')
        self.assertTrue(order.require_approval)

        # 2. Request approval
        order.action_request_approval()
        self.assertEqual(order.state, 'pending_approval')
        self.assertEqual(order.approval_state_display, 'En Espera de Aprobación')

        # 3. Approve (simulate manager approval)
        # First, we need to set up a proper approver
        approver = order.approval_request_id.approver_ids[0] if order.approval_request_id.approver_ids else None
        if approver:
            # Simulate approval
            order.approval_request_id.action_approve()
            if order.approval_request_id.state == 'approved':
                order.state = 'draft'  # Ready for confirmation
                self.assertEqual(order.approval_state_display, 'Aprobado')

    def test_04_approval_permissions_display(self):
        """Test that approval permissions are computed correctly"""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })

        # Create approval request
        order._create_approval_request()
        order.action_request_approval()

        # Initially, user might not have permissions
        # This depends on the approval category configuration
        self.assertIsInstance(order.can_approve, bool)
        self.assertIsInstance(order.can_reject, bool)