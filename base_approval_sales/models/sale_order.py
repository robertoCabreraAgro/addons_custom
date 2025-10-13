import logging

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    """Sales Order with centralized approval workflow."""
    _inherit = "sale.order"

    # ============================================================
    # FIELDS - DEFENSIVE APPROACH + REAL WORKFLOW INTEGRATION
    # ============================================================

    approval_request_id = fields.Many2one(
        comodel_name="approval.request",
        string="Approval Request",
        help="Related approval request for this sale order",
        copy=False,
        readonly=True,
    )


    state = fields.Selection(
        selection_add=[
            ('pending_approval', 'En Espera de Aprobación'),
            ('approved', 'Aprobado'),
            ('refused', 'Rechazado'),
        ],
        ondelete={
            'pending_approval': 'set draft',
            'approved': 'set draft',
            'refused': 'set draft',
        },
    )

    approval_state_display = fields.Char(
        string="Estado de Aprobación",
        compute="_compute_approval_state_display",
        help="Estado de aprobación legible en español",
    )

    require_approval = fields.Boolean(
        string="Requiere Aprobación",
        compute="_compute_require_approval",
        store=True,
        help="Indica si esta cotización requiere aprobación antes de confirmar",
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
        try:
            return 'approval.request' in self.env
        except:
            return False

    def _get_approval_request(self):
        """Get the related approval request safely."""
        if not self._approval_system_available() or not self.approval_request_id:
            return None

        return self.approval_request_id

    def _set_approval_request(self, approval_request):
        """Set the approval request reference safely."""
        self.approval_request_id = approval_request.id if approval_request else False

    def _get_approval_state(self):
        """Get current approval state safely."""
        request = self._get_approval_request()
        if request and request.exists():
            return request.state
        return None

    # ============================================================
    # COMPUTE METHODS
    # ============================================================

    @api.depends("approval_request_id", "state")
    def _compute_approval_state_display(self):
        """Compute human readable approval state in Spanish."""
        state_translations = {
            'new': 'Sin Solicitar',
            'pending': 'En Espera de Aprobación',
            'approved': 'Aprobado',
            'refused': 'Rechazado',
            'cancel': 'Cancelado'
        }
        for order in self:
            if not order._approval_system_available():
                order.approval_state_display = 'Sistema no disponible'
                continue

            # Sync with real state
            if order.state == 'pending_approval':
                approval_state = order._get_approval_state() or 'pending'
            elif order.state == 'approved':
                approval_state = 'approved'
            elif order.state == 'refused':
                approval_state = 'refused'
            else:
                approval_state = order._get_approval_state() or 'new'

            order.approval_state_display = state_translations.get(
                approval_state, 'Sin Definir'
            )

    @api.depends()
    def _compute_require_approval(self):
        """ALL orders require approval without exceptions."""
        for order in self:
            # Force all orders to require approval without exception
            order.require_approval = order._approval_system_available()

    @api.depends_context("uid")
    @api.depends("approval_request_id", "state")
    def _compute_approval_permissions(self):
        """Compute approval permissions for current user."""
        for order in self:
            can_approve = can_reject = False

            if (order._approval_system_available() and
                order.state == 'pending_approval' and
                order._get_approval_state() == "pending"):

                try:
                    request = order._get_approval_request()
                    if request and request.exists():
                        # Check if current user is an approver
                        user_approver = request.approver_ids.filtered(
                            lambda a: a.user_id == self.env.user and a.status == "pending"
                        )
                        can_approve = can_reject = bool(user_approver)
                except:
                    pass

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
            if order.require_approval and not order.approval_request_id:
                try:
                    order._create_approval_request_auto()
                except UserError:
                    # Re-raise UserError to inform user of configuration issues
                    raise
                except Exception:
                    # Defensive: don't break order creation for unexpected errors
                    pass

        return orders

    def write(self, vals):
        """CRITICAL FIX: Handle approval workflow changes."""
        result = super().write(vals)

        # Check if order lines or partner change requiring re-approval
        approval_relevant_fields = [
            "order_line", "partner_id"
        ]

        if any(field in vals for field in approval_relevant_fields):
            for order in self:
                if (order.require_approval and
                    not order.approval_request_id and
                    order.state in ('draft', 'sent')):
                    try:
                        order._create_approval_request_auto()
                    except UserError:
                        # Re-raise UserError to inform user of configuration issues
                        raise
                    except Exception:
                        # Defensive: don't break updates for unexpected errors
                        pass

        return result

    def action_confirm(self):
        """CRITICAL FIX: Real workflow validation."""
        for order in self:
            if order.require_approval:
                # Real state validation
                if order.state == 'pending_approval':
                    raise UserError(_(
                        "Esta cotización está pendiente de aprobación.\n"
                        "Estado actual: %s"
                    ) % (order.approval_state_display or "Pendiente"))

                elif order.state == 'refused':
                    raise UserError(_(
                        "Esta cotización ha sido rechazada.\n"
                        "Debe solicitar una nueva aprobación para continuar."
                    ))

                elif not order.approval_request_id:
                    raise UserError(_(
                        "Esta cotización requiere aprobación.\n"
                        "Por favor, solicite la aprobación antes de confirmar."
                    ))

                elif order.state != 'approved':
                    raise UserError(_(
                        "Solo las cotizaciones aprobadas pueden ser confirmadas.\n"
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

        existing_request = self._get_approval_request()
        if existing_request and existing_request.exists():
            approval_state = existing_request.state
            if approval_state == "pending":
                raise UserError(_("Ya existe una solicitud de aprobación pendiente."))
            elif approval_state == "approved":
                raise UserError(_("Esta cotización ya está aprobada."))

        # Create approval request
        self._create_approval_request_auto()

        # CRITICAL FIX: Update real state
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

        request = self._get_approval_request()
        if not request or not request.exists() or request.state != "pending":
            raise UserError(_("No hay una solicitud de aprobación pendiente."))

        try:
            # Find user's approver record and approve
            user_approver = request.approver_ids.filtered(
                lambda a: a.user_id == self.env.user and a.status == "pending"
            )

            if not user_approver:
                raise UserError(_("No se encontró su registro de aprobador."))

            user_approver.action_approve()

            # CRITICAL FIX: Update real state when fully approved
            if request.state == "approved":
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

        request = self._get_approval_request()
        if not request or not request.exists() or request.state != "pending":
            raise UserError(_("No hay una solicitud de aprobación pendiente."))

        try:
            # Find user's approver record and reject
            user_approver = request.approver_ids.filtered(
                lambda a: a.user_id == self.env.user and a.status == "pending"
            )

            if not user_approver:
                raise UserError(_("No se encontró su registro de aprobador."))

            user_approver.action_refuse()

            # CRITICAL FIX: Update real state when rejected
            self.write({'state': 'refused'})  # Mark as refused

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

        request = self._get_approval_request()
        if not request or not request.exists():
            raise UserError(_("No hay solicitud de aprobación asociada."))

        return {
            "name": _("Solicitud de Aprobación"),
            "type": "ir.actions.act_window",
            "res_model": "approval.request",
            "res_id": request.id,
            "view_mode": "form",
            "target": "new",
            "context": {"create": False, "edit": False},
        }

    # ============================================================
    # HELPER METHODS - AUTO-CREATION LOGIC
    # ============================================================

    def _create_approval_request_auto(self):
        """Auto-create approval request using existing 'Sale Quotation' category.

        Returns:
            approval.request: The created approval request

        Raises:
            UserError: If category doesn't exist or creation fails
        """
        self.ensure_one()

        if self.approval_request_id:
            return self._get_approval_request()

        # Get the existing approval category (will raise UserError if not found)
        category = self._get_approval_category()
        _logger.debug("Using approval category '%s' (ID: %s) for sale order %s",
                     category.name, category.id, self.name)

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

        try:
            _logger.debug("Creating approval request with values: %s", approval_vals)
            approval_request = self.env["approval.request"].create(approval_vals)

            _logger.info("Successfully created approval request %s for sale order %s",
                        approval_request.name, self.name)

            # Link to sale order
            self._set_approval_request(approval_request)

            return approval_request

        except Exception as e:
            _logger.error("Failed to create approval request for sale order %s: %s",
                         self.name, str(e), exc_info=True)
            raise UserError(_(
                "Error al crear la solicitud de aprobación: %s\n"
                "Categoría utilizada: '%s' (ID: %s)\n"
                "Verifique que la categoría 'Sale Quotation' esté configurada correctamente."
            ) % (str(e), category.name, category.id))

    def _should_auto_request_approval(self):
        """ALL orders must auto-request approval."""
        # Always return True - no conditions of amount
        return True

    def _get_approval_category(self):
        """Get the sales order approval category with robust search.

        This method searches for the 'Sale Quotation' category using multiple
        strategies to ensure maximum compatibility:
        1. Search by name and company (preferred)
        2. Search by name only (fallback)
        3. Search ignoring case sensitivity

        Returns:
            approval.category: The 'Sale Quotation' category

        Raises:
            UserError: If the required category doesn't exist
        """
        if not self._approval_system_available():
            raise UserError(_("Sistema de aprobaciones no disponible."))

        category = None

        # Strategy 1: Search by name and company (exact match)
        _logger.debug("Searching for 'Sale Quotation' category for company %s", self.company_id.name)
        category = self.env["approval.category"].search([
            ("name", "=", "Sale Quotation"),
            ("company_id", "=", self.company_id.id),
            ("active", "=", True),
        ], limit=1)

        if category:
            _logger.debug("Found category %s (ID: %s) for company %s",
                         category.name, category.id, self.company_id.name)
            return category

        # Strategy 2: Search by name only (fallback for multi-company)
        _logger.debug("No company-specific category found, searching globally")
        category = self.env["approval.category"].search([
            ("name", "=", "Sale Quotation"),
            ("active", "=", True),
        ], limit=1)

        if category:
            _logger.info("Found global 'Sale Quotation' category (ID: %s, Company: %s)",
                        category.id, category.company_id.name if category.company_id else 'Global')
            return category

        # Strategy 3: Case-insensitive search as last resort
        _logger.debug("No exact match found, trying case-insensitive search")
        category = self.env["approval.category"].search([
            ("name", "ilike", "Sale Quotation"),
            ("active", "=", True),
        ], limit=1)

        if category:
            _logger.warning("Found category with similar name: '%s' (ID: %s)",
                           category.name, category.id)
            return category

        # Log available categories for debugging
        all_categories = self.env["approval.category"].search([
            ("active", "=", True)
        ])
        category_names = [cat.name for cat in all_categories]
        _logger.error("No 'Sale Quotation' category found. Available categories: %s",
                     category_names)

        raise UserError(_(
            "No se encontró la categoría de aprobación 'Sale Quotation'.\n"
            "Categorías disponibles: %s\n"
            "Por favor, verifique que la categoría exista y esté activa."
        ) % ", ".join(category_names[:5]))  # Show max 5 categories to avoid UI clutter

