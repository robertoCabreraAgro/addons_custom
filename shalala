import logging

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    """Sales Order with centralized approval workflow."""
    _inherit = "sale.order"

    # ============================================================
    # FIELDS - Sales Approval Integration
    # ============================================================

    approval_request_ref = fields.Many2one(
        'approval.request',
        string='Approval Request',
        help="Linked approval request for this sales order",
        copy=False,
        readonly=True,
    )

    require_approval = fields.Boolean(
        string='Requiere Aprobación',
        default=True,
        help="All sales orders require approval by default",
    )

    # Extended state to include approval workflow states
    state = fields.Selection(
        selection_add=[
            ('pending_approval', 'En Espera de Aprobación'),
            ('approved', 'Aprobado'),
        ],
        ondelete={
            'pending_approval': 'set draft',
            'approved': 'set draft'
        },
    )

    approval_state = fields.Char(
        string='Approval State',
        compute='_compute_approval_state',
        store=False,
        help="Current approval state from approval request",
    )

    approval_state_display = fields.Char(
        string='Estado de Aprobación',
        compute='_compute_approval_state_display',
        store=False,
        help="Current approval state in Spanish",
    )

    can_approve = fields.Boolean(
        string="Puede Aprobar",
        compute="_compute_approval_permissions",
        help="El usuario actual puede aprobar esta cotización",
    )

    can_reject = fields.Boolean(
        string="Puede Rechazar",
        compute="_compute_approval_permissions",
        help="El usuario actual puede rechazar esta cotización",
    )

    # ============================================================
    # HELPER METHODS - SAFE ACCESS TO APPROVAL SYSTEM
    # ============================================================

    def _approval_system_available(self):
        """Check if approval system is available safely for Odoo 18."""
        try:
            return ('approval.request' in self.env and
                    'approval.category' in self.env)
        except Exception:
            return False

    def _get_approval_request(self):
        """Get the related approval request safely."""
        if not self._approval_system_available() or not self.approval_request_ref:
            return None
        return self.approval_request_ref

    def _set_approval_request(self, approval_request):
        """Set the approval request reference safely."""
        self.approval_request_ref = approval_request.id if approval_request else False

    def _get_approval_state(self):
        """Get current approval state safely."""
        if self.approval_request_ref and self.approval_request_ref.exists():
            return self.approval_request_ref.state
        return None

    # ============================================================
    # COMPUTE METHODS
    # ============================================================

    @api.depends('approval_request_ref', 'approval_request_ref.state')
    def _compute_approval_state(self):
        """Compute approval state directly from approval request state.

        ODOO 18 COMPATIBLE: Ensures ALL records receive a value assignment.
        """
        for order in self:
            # Initialize with default value - GUARANTEED assignment
            approval_state = 'new'

            try:
                # Check if approval system is available and approval request exists
                if (order._approval_system_available() and
                    order.approval_request_ref and
                    hasattr(order.approval_request_ref, 'exists') and
                    order.approval_request_ref.exists()):
                    # Get state from approval request
                    approval_state = getattr(order.approval_request_ref, 'state', 'new')
                else:
                    # No approval request exists or system unavailable
                    approval_state = 'new'

            except Exception:
                # Exception fallback - still assigns value
                approval_state = 'new'

            # GUARANTEED assignment for every record - CRITICAL FOR ODOO 18
            order.approval_state = approval_state

    @api.depends('approval_request_ref', 'approval_request_ref.state', 'state')
    def _compute_approval_state_display(self):
        """Compute readable approval state based on sale order and approval request state.

        ODOO 18 COMPATIBLE: Ensures ALL records receive a value assignment.
        """
        for order in self:
            # Initialize with default value - GUARANTEED assignment
            approval_state_display = 'Sin Definir'

            try:
                # Check if approval system is available
                if not order._approval_system_available():
                    approval_state_display = 'Sistema no disponible'

                # Priority 1: Check sale order state first (most reliable)
                elif order.state == 'pending_approval':
                    approval_state_display = 'En Espera de Aprobación'
                elif order.state == 'approved':
                    approval_state_display = 'Aprobado'
                elif order.state == 'cancel':
                    approval_state_display = 'Cancelado'
                elif order.state in ('draft', 'sent'):
                    # Check if there's an approval request
                    if order.approval_request_ref:
                        # There is a request, check its state
                        try:
                            if (hasattr(order.approval_request_ref, 'exists') and
                                order.approval_request_ref.exists()):
                                approval_state = getattr(order.approval_request_ref, 'state', None)
                                if approval_state == 'refused':
                                    approval_state_display = 'Rechazado'
                                elif approval_state == 'approved':
                                    approval_state_display = 'Aprobado'
                                elif approval_state == 'pending':
                                    approval_state_display = 'En Espera de Aprobación'
                                else:
                                    approval_state_display = 'Sin Solicitar'
                            else:
                                approval_state_display = 'Sin Solicitar'
                        except Exception:
                            approval_state_display = 'Sin Solicitar'
                    else:
                        # No approval request exists
                        approval_state_display = 'Sin Solicitar'

                # Priority 2: Check other sale order states
                elif order.state in ('sale', 'done'):
                    approval_state_display = 'Confirmado'
                else:
                    # Any other state
                    approval_state_display = 'Sin Definir'

            except Exception:
                # Exception fallback - still assigns value
                approval_state_display = 'Error'

            # GUARANTEED assignment for every record - CRITICAL FOR ODOO 18
            order.approval_state_display = approval_state_display


    @api.depends_context('uid')
    @api.depends('approval_request_ref', 'approval_request_ref.approver_ids', 'state')
    def _compute_approval_permissions(self):
        """Compute approval permissions for current user.

        ODOO 18 COMPATIBLE: Ensures ALL records receive value assignment.
        """
        for order in self:
            # Initialize with default values - GUARANTEED assignment
            can_approve = False
            can_reject = False

            try:
                # Check all conditions safely with proper attribute checking
                if (order._approval_system_available() and
                    order.state == 'pending_approval' and
                    order.approval_request_ref and
                    hasattr(order.approval_request_ref, 'exists') and
                    order.approval_request_ref.exists() and
                    hasattr(order.approval_request_ref, 'state') and
                    getattr(order.approval_request_ref, 'state', None) == 'pending'):

                    # Safely check approver_ids with defensive programming
                    approver_ids = getattr(order.approval_request_ref, 'approver_ids', None)
                    if approver_ids:
                        try:
                            user_approver = approver_ids.filtered(
                                lambda a: (hasattr(a, 'user_id') and
                                         hasattr(a, 'status') and
                                         getattr(a, 'user_id', None) == self.env.user and
                                         getattr(a, 'status', None) == 'pending')
                            )
                            can_approve = can_reject = bool(user_approver)
                        except Exception:
                            # Filtered operation failed - keep defaults
                            pass

            except Exception:
                # Exception fallback - still assigns default values
                can_approve = can_reject = False

            # GUARANTEED assignment for every record
            order.can_approve = can_approve
            order.can_reject = can_reject

    # ============================================================
    # OVERRIDE METHODS - AUTO-CREATION + REAL WORKFLOW
    # ============================================================

    @api.model_create_multi
    def create(self, vals_list):
        """CRITICAL FIX: Auto-create approval requests."""
        orders = super().create(vals_list)

        for order in orders:
            if order.require_approval and not order.approval_request_ref:
                try:
                    order._create_approval_request_auto()
                except Exception:
                    # Defensive: don't break order creation if approval fails
                    pass

        return orders

    def write(self, vals):
        """CRITICAL FIX: Handle approval workflow changes."""
        result = super().write(vals)

        # Check if order lines or amounts change requiring re-approval
        approval_relevant_fields = [
            "order_line", "amount_total", "amount_untaxed", "partner_id"
        ]

        if any(field in vals for field in approval_relevant_fields):
            for order in self:
                if (order.require_approval and
                    not order.approval_request_ref and
                    order.state in ('draft', 'sent')):
                    try:
                        order._create_approval_request_auto()
                    except Exception:
                        # Defensive: don't break updates
                        pass

        return result

    def action_confirm(self):
        """Validate approval workflow before confirming order."""
        for order in self:
            if order.require_approval:
                # Check if order is in pending approval state
                if order.state == 'pending_approval':
                    raise UserError(_(
                        "Esta cotización está pendiente de aprobación.\n"
                        "Estado actual: %s"
                    ) % (order.approval_state_display or "Pendiente"))

                # Check if order needs approval but hasn't been requested
                elif order.state in ('draft', 'sent') and not order.approval_request_ref:
                    raise UserError(_(
                        "Esta cotización requiere aprobación.\n"
                        "Por favor, solicite la aprobación antes de confirmar."
                    ))

                # Check if order is not in approved state
                elif order.state != 'approved':
                    raise UserError(_(
                        "No puede confirmar esta cotización hasta que sea aprobada.\n"
                        "Estado actual: %s"
                    ) % (order.approval_state_display or "Sin aprobar"))

        return super().action_confirm()

    # ============================================================
    # APPROVAL WORKFLOW ACTIONS - ENHANCED
    # ============================================================

    def action_request_approval(self):
        """Create and submit approval request for this order."""
        self.ensure_one()

        if not self._approval_system_available():
            raise UserError(_("Sistema de aprobaciones no disponible."))

        if not self.require_approval:
            raise UserError(_("Esta cotización no requiere aprobación."))

        if self.approval_request_ref:
            approval_state = self.approval_request_ref.state
            if approval_state == "pending":
                raise UserError(_("Ya existe una solicitud de aprobación pendiente."))
            elif approval_state == "approved":
                raise UserError(_("Esta cotización ya está aprobada."))

        # Create approval request
        self._create_approval_request_auto()

        # Update real state
        self.write({'state': 'pending_approval'})

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("✅ Solicitud Enviada"),
                "message": _("La solicitud de aprobación ha sido enviada correctamente."),
                "type": "success",
                "sticky": False,
            },
        }

    def action_approve(self):
        """CRITICAL FIX: Approve with real state transition."""
        self.ensure_one()

        if not self._approval_system_available():
            raise UserError(_("Sistema de aprobaciones no disponible."))

        if not self.can_approve:
            raise UserError(_("No tiene permisos para aprobar esta cotización."))

        if not self.approval_request_ref or self.approval_request_ref.state != "pending":
            raise UserError(_("No hay una solicitud de aprobación pendiente."))

        try:
            # Find user's approver record and approve
            user_approver = self.approval_request_ref.approver_ids.filtered(
                lambda a: a.user_id == self.env.user and a.status == "pending"
            )

            if not user_approver:
                raise UserError(_("No se encontró su registro de aprobador."))

            user_approver.action_approve()

            # Update real state when fully approved
            if self.approval_request_ref.state == "approved":
                self.write({'state': 'approved'})  # Ready for confirmation

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("✅ Aprobado"),
                    "message": _("La cotización ha sido aprobada correctamente."),
                    "type": "success",
                    "sticky": False,
                },
            }
        except Exception as e:
            raise UserError(_("Error al aprobar: %s") % str(e))

    def action_reject(self):
        """CRITICAL FIX: Reject with real state transition."""
        self.ensure_one()

        if not self._approval_system_available():
            raise UserError(_("Sistema de aprobaciones no disponible."))

        if not self.can_reject:
            raise UserError(_("No tiene permisos para rechazar esta cotización."))

        if not self.approval_request_ref or self.approval_request_ref.state != "pending":
            raise UserError(_("No hay una solicitud de aprobación pendiente."))

        try:
            # Find user's approver record and reject
            user_approver = self.approval_request_ref.approver_ids.filtered(
                lambda a: a.user_id == self.env.user and a.status == "pending"
            )

            if not user_approver:
                raise UserError(_("No se encontró su registro de aprobador."))

            user_approver.action_refuse()

            # Update real state when rejected
            self.write({'state': 'draft'})  # Back to draft for modification

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("❌ Rechazado"),
                    "message": _("La cotización ha sido rechazada."),
                    "type": "warning",
                    "sticky": False,
                },
            }
        except Exception as e:
            raise UserError(_("Error al rechazar: %s") % str(e))

    def action_view_approval_request(self):
        """Open the related approval request."""
        self.ensure_one()

        if not self._approval_system_available():
            raise UserError(_("Sistema de aprobaciones no disponible."))

        if not self.approval_request_ref:
            raise UserError(_("No hay solicitud de aprobación asociada."))

        return {
            "name": _("Solicitud de Aprobación"),
            "type": "ir.actions.act_window",
            "res_model": "approval.request",
            "res_id": self.approval_request_ref.id,
            "view_mode": "form",
            "target": "new",
            "context": {"create": False, "edit": False},
        }

    # ============================================================
    # HELPER METHODS - AUTO-CREATION LOGIC
    # ============================================================

    def _create_approval_request(self):
        """Create approval request for this order (method expected by tests)."""
        return self._create_approval_request_auto()

    def _create_approval_request_auto(self):
        """CRITICAL FIX: Auto-create approval request."""
        self.ensure_one()

        if self.approval_request_ref:
            return self.approval_request_ref

        # Get or create approval category
        category = self._get_approval_category()
        if not category:
            raise UserError(_(
                "No se pudo crear la categoría de aprobación.\n\n"
                "Posibles causas:\n"
                "• Permisos insuficientes para crear categorías de aprobación\n"
                "• Error en la configuración del sistema de aprobaciones\n"
                "• Faltan campos obligatorios en la categoría\n\n"
                "Contacte al administrador del sistema para revisar los logs."
            ))

        # Create approval request
        approval_vals = {
            "name": _("Aprobación de Cotización: %s") % self.name,
            "category_id": category.id,
            "request_owner_id": self.user_id.id or self.env.user.id,
            "partner_id": self.partner_id.id if self.partner_id else False,
            "amount": self.amount_total,
            "reference": self.name,
            "reason": _("Solicitud de aprobación para la cotización %s por un monto de $%.2f") % (
                self.name, self.amount_total
            ),
            "date": fields.Datetime.now(),
            "company_id": self.company_id.id,
        }

        approval_request = self.env["approval.request"].create(approval_vals)

        # Link to sale order
        self.approval_request_ref = approval_request.id

        return approval_request

    def _should_auto_request_approval(self):
        """All orders should auto-request approval - no configuration needed."""
        # Always return True - all orders require approval without exception
        return True

    def _get_approval_category(self):
        """Get or create the sales order approval category."""
        if not self._approval_system_available():
            _logger.warning("Approval system not available for sale order %s", self.name)
            return None

        try:
            category = self.env["approval.category"].search([
                ("name", "=", "Sales Order Approval"),
                ("company_id", "=", self.company_id.id),
            ], limit=1)

            if not category:
                _logger.info("Creating new approval category for company %s", self.company_id.name)
                category = self._create_default_approval_category()
                if category:
                    _logger.info("Successfully created approval category ID %s", category.id)

            return category
        except Exception as e:
            _logger.error(
                "Error in _get_approval_category for sale order %s: %s",
                self.name, str(e)
            )
            return None

    def _create_default_approval_category(self):
        """Create default approval category for sales orders."""
        try:
            # Find sales managers to assign as default approvers
            try:
                sales_managers = self.env.ref("sales_team.group_sale_manager").users
            except ValueError:
                sales_managers = self.env.ref("base.user_admin")

            if not sales_managers:
                sales_managers = self.env.ref("base.user_admin")

            # Complete category_vals with ALL required fields to avoid ValidationError
            category_vals = {
                "name": "Sales Order Approval",
                "company_id": self.company_id.id,
                # Required fields for amounts and references (what we need)
                "has_amount": "required",
                "has_partner": "required",
                "has_reference": "required",
                # All other required fields set to "no" (not needed for sales orders)
                "has_date": "no",
                "has_date_deadline": "no",
                "has_date_planned": "no",
                "has_date_range": "no",
                "has_payment_method": "no",
                "has_product": "no",
                "has_quantity": "no",
                "has_location": "no",
                "has_document": "optional",
                "approval_minimum": 1,
                "automated_sequence": True,
                "sequence_code": "SO-APPR-",
                "description": "Categoría de aprobación para todas las órdenes de venta",
            }

            # Use sudo() to bypass permission restrictions for category creation
            category = self.env["approval.category"].sudo().create(category_vals)

            # Create default approver (also with sudo for approver creation)
            for i, manager in enumerate(sales_managers[:3]):  # Max 3 approvers
                self.env["approval.category.approver"].sudo().create({
                    "category_id": category.id,
                    "user_id": manager.id,
                    "required": i == 0,  # First one is required
                    "sequence": (i + 1) * 10,
                })

            return category
        except Exception as e:
            _logger.error(
                "Error creating approval category for sale order %s: %s",
                self.name, str(e)
            )
            return None

