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
    # APPROVAL CATEGORY MANAGEMENT - USES EXISTING "Sale Quotation" CATEGORY
    # ============================================================

    def _get_approval_category(self):
        """Get the existing 'Sale Quotation' approval category.

        Returns:
            approval.category: The existing 'Sale Quotation' category

        Raises:
            UserError: If the 'Sale Quotation' category does not exist
        """
        self.ensure_one()

        # Search for the existing 'Sale Quotation' category
        # NOTE: We do NOT create categories - only use existing ones
        category = self.env['approval.category'].search([
            ('name', '=', 'Sale Quotation'),
            ('company_id', 'in', [self.company_id.id, False])
        ], limit=1)

        if not category:
            raise UserError(_(
                "No se encontró la categoría de aprobación 'Sale Quotation'.\n\n"
                "Para usar el sistema de aprobaciones, debe existir una categoría "
                "llamada 'Sale Quotation' configurada correctamente.\n\n"
                "Contacte al administrador para crear esta categoría en:\n"
                "Aplicaciones → Aprobaciones → Configuración → Categorías de Aprobación"
            ))

        _logger.info("Found existing approval category 'Sale Quotation' (ID: %s) for sale order %s",
                    category.id, self.name)
        return category

    # ============================================================
    # COMPUTE METHODS
    # ============================================================

    @api.depends('approval_request_ref', 'approval_request_ref.state')
    def _compute_approval_state(self):
        """Compute approval state directly from linked approval request."""
        for order in self:
            # Default state if no approval request exists
            approval_state = 'new'

            try:
                # Get state from approval request if it exists
                if order.approval_request_ref and order.approval_request_ref.exists():
                    approval_state = order.approval_request_ref.state or 'new'
            except Exception:
                approval_state = 'new'

            order.approval_state = approval_state

    @api.depends('approval_request_ref', 'approval_request_ref.state', 'state')
    def _compute_approval_state_display(self):
        """Compute readable approval state in Spanish based on current states."""
        for order in self:
            # Determine display text based on sale order and approval request states
            if order.state == 'pending_approval':
                approval_state_display = 'En Espera de Aprobación'
            elif order.state == 'approved':
                approval_state_display = 'Aprobado'
            elif order.state == 'cancel':
                approval_state_display = 'Cancelado'
            elif order.state in ('sale', 'done'):
                approval_state_display = 'Confirmado'
            elif order.state in ('draft', 'sent'):
                # Check approval request state for draft/sent orders
                if order.approval_request_ref and order.approval_request_ref.exists():
                    approval_state = order.approval_request_ref.state
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
            else:
                approval_state_display = 'Sin Definir'

            order.approval_state_display = approval_state_display


    @api.depends_context('uid')
    @api.depends('approval_request_ref', 'approval_request_ref.approver_ids', 'state')
    def _compute_approval_permissions(self):
        """Compute approval permissions for current user based on approval request.

        Determines if the current user can approve or reject the quotation
        based on their role as an approver in the linked approval request.
        """
        for order in self:
            # Initialize with default values
            can_approve = False
            can_reject = False

            try:
                # Check if order is in pending approval state with valid approval request
                if (order.state == 'pending_approval' and
                    order.approval_request_ref and
                    order.approval_request_ref.exists() and
                    order.approval_request_ref.state == 'pending'):

                    # Check if current user is a pending approver
                    user_approver = order.approval_request_ref.approver_ids.filtered(
                        lambda a: a.user_id == self.env.user and a.status == 'pending'
                    )
                    can_approve = can_reject = bool(user_approver)

            except Exception:
                # Exception fallback - keep defaults
                can_approve = can_reject = False

            # Assign computed values
            order.can_approve = can_approve
            order.can_reject = can_reject

    # ============================================================
    # OVERRIDE METHODS - AUTO-CREATION + REAL WORKFLOW
    # ============================================================

    @api.model_create_multi
    def create(self, vals_list):
        """Create sale orders and automatically generate approval requests.

        For each sale order that requires approval (require_approval=True),
        this method automatically creates an approval.request linked to the
        existing 'Sale Quotation' category.

        NOTE: This uses existing approval categories only - no dynamic creation.
        """
        orders = super().create(vals_list)

        for order in orders:
            if order.require_approval and not order.approval_request_ref:
                try:
                    # Create approval request using existing 'Sale Quotation' category
                    order._create_approval_request()
                    _logger.info("Auto-created approval request for sale order %s", order.name)
                except UserError as e:
                    # Log the specific error but don't break sale order creation
                    _logger.warning("Failed to auto-create approval request for sale order %s: %s",
                                  order.name, str(e))
                except Exception as e:
                    # Log unexpected errors but don't break sale order creation
                    _logger.error("Unexpected error auto-creating approval request for sale order %s: %s",
                                order.name, str(e), exc_info=True)

        return orders

    def write(self, vals):
        """Handle approval workflow when order changes occur.

        If approval-relevant fields change (order lines, amounts, partner),
        and the order requires approval but doesn't have an approval request,
        automatically create one using the existing 'Sale Quotation' category.
        """
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
                        # Create approval request using existing 'Sale Quotation' category
                        order._create_approval_request()
                        _logger.info("Auto-created approval request for modified sale order %s", order.name)
                    except UserError as e:
                        # Log the specific error but don't break order updates
                        _logger.warning("Failed to auto-create approval request for modified sale order %s: %s",
                                      order.name, str(e))
                    except Exception as e:
                        # Log unexpected errors but don't break order updates
                        _logger.error("Unexpected error auto-creating approval request for modified sale order %s: %s",
                                    order.name, str(e), exc_info=True)

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
        """Create and submit approval request using existing 'Sale Quotation' category."""
        self.ensure_one()

        if not self.require_approval:
            raise UserError(_("Esta cotización no requiere aprobación."))

        if self.approval_request_ref:
            approval_state = self.approval_request_ref.state
            if approval_state == "pending":
                raise UserError(_("Ya existe una solicitud de aprobación pendiente."))
            elif approval_state == "approved":
                raise UserError(_("Esta cotización ya está aprobada."))

        # Create approval request using existing 'Sale Quotation' category
        # This will raise UserError if category doesn't exist
        self._create_approval_request()

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
        """Approve the quotation through the approval request system."""
        self.ensure_one()

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

            # Update sale order state when fully approved
            if self.approval_request_ref.state == "approved":
                self.state = 'approved'  # Ready for confirmation

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
        """Reject the quotation through the approval request system."""
        self.ensure_one()

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

            # Update sale order state when rejected
            self.state = 'draft'  # Back to draft for modification

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
    # APPROVAL REQUEST CREATION - USES EXISTING "Sale Quotation" CATEGORY
    # ============================================================

    def _create_approval_request(self):
        """Create approval request linked to existing 'Sale Quotation' category.

        This method creates an approval.request record for the current sale order
        using the existing 'Sale Quotation' approval category. It does NOT create
        new categories - only uses pre-configured ones.

        Returns:
            approval.request: The created approval request record

        Raises:
            UserError: If 'Sale Quotation' category doesn't exist or creation fails
        """
        self.ensure_one()

        # Check if approval request already exists
        if self.approval_request_ref:
            _logger.debug("Approval request already exists for sale order %s", self.name)
            return self.approval_request_ref

        # Get the existing 'Sale Quotation' category (raises UserError if not found)
        category = self._get_approval_category()

        # Prepare approval request values
        approval_vals = {
            "name": _("Aprobación de Cotización: %s") % self.name,
            "category_id": category.id,
            "request_owner_id": self.user_id.id or self.env.user.id,
            "partner_id": self.partner_id.id if self.partner_id else False,
            "amount": self.amount_total or 0.0,
            "reference": self.name,
            "reason": _("Solicitud de aprobación para la cotización %s por un monto de $%.2f") % (
                self.name, self.amount_total or 0.0
            ),
            "date": fields.Datetime.now(),
            "company_id": self.company_id.id,
        }

        _logger.info("Creating approval request for sale order %s using category 'Sale Quotation' (ID: %s)",
                    self.name, category.id)

        try:
            # Create approval request - NO sudo() used, respects user permissions
            approval_request = self.env["approval.request"].create(approval_vals)

            # Link approval request to sale order
            self.approval_request_ref = approval_request.id

            # Update sale order state to pending approval
            self.state = 'pending_approval'

            _logger.info("Successfully created approval request ID %s for sale order %s",
                        approval_request.id, self.name)

            return approval_request

        except Exception as e:
            error_message = _(
                "Error al crear la solicitud de aprobación.\n\n"
                "Detalle: %s\n\n"
                "Verifique que tenga permisos para crear solicitudes de aprobación."
            ) % str(e)
            _logger.error("Error creating approval request for sale order %s: %s",
                         self.name, str(e), exc_info=True)
            raise UserError(error_message)


