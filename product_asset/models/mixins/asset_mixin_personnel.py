import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class AssetMixinPersonnel(models.AbstractModel):
    """Personnel assignment mixin for asset management

    This mixin handles all personnel-related aspects of assets:
    - Current operator/driver assignments
    - Asset manager assignments
    - Future operator workflows
    - Assignment history tracking
    - Assignment date management
    """

    _name = "asset.mixin.personnel"
    _description = "Asset Personnel Mixin"

    # ------------------------------------------------------------
    # CURRENT ASSIGNMENTS
    # ------------------------------------------------------------

    operator_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Current Driver/Operator",
        domain='[("company_id", "in", (company_id, False))]',
        copy=False,
        tracking=True,
        help="Employee currently assigned as the primary operator of this asset",
    )
    asset_manager_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Asset Manager",
        domain=lambda self: [
            ("company_id", "in", self.env.companies.ids),
        ],
        copy=False,
        tracking=True,
        help="Employee responsible for managing and overseeing this asset",
    )

    # ------------------------------------------------------------
    # FUTURE ASSIGNMENT WORKFLOW
    # ------------------------------------------------------------

    future_operator_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Future Driver/Operator",
        domain='[("company_id", "in", (company_id, False))]',
        copy=False,
        tracking=True,
        help="Next assigned operator (pending assignment date)",
    )
    date_next_assignation = fields.Date(
        string="Next Assignment Date",
        help="Date when the future operator will take over the asset",
    )

    # ------------------------------------------------------------
    # CONSTRAINTS
    # ------------------------------------------------------------

    @api.constrains("future_operator_id", "operator_id")
    def _check_future_operator(self):
        """Ensure future operator is different from current"""
        for record in self:
            if (
                record.future_operator_id
                and record.future_operator_id == record.operator_id
            ):
                raise models.ValidationError(
                    _("Future operator cannot be the same as current operator.")
                )

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    @api.onchange("future_operator_id")
    def _onchange_future_operator(self):
        """Validate future operator selection"""
        if self.future_operator_id:
            # Suggest assignment date if not set
            if not self.date_next_assignation:
                self.date_next_assignation = fields.Date.today()

            # Validate not same as current
            if self.future_operator_id == self.operator_id:
                raise models.ValidationError(
                    _("Future operator cannot be the same as current operator.")
                )

    # ------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------

    def action_clear_operator(self):
        """Action to clear the current operator assignment"""
        for asset in self:
            if asset.operator_id:
                old_operator = asset.operator_id

                # Create log for removal
                asset._create_assignment_log(
                    old_operator=old_operator, new_operator=False, change_type="removal"
                )

                # Clear operator
                asset.operator_id = False

                # Send notification
                asset._notify_operator_change(old_operator, False)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Operator Removed"),
                "message": _("Operator has been removed from the asset."),
                "type": "info",
                "sticky": False,
            },
        }

    def action_schedule_assignment(self):
        """Open a wizard to schedule future operator assignment"""
        self.ensure_one()

        # This would open a wizard for scheduling
        # For now, just ensure fields are visible
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Schedule Assignment"),
                "message": _(
                    "Set the Future Operator and Assignment Date, then click Accept Assignment."
                ),
                "type": "info",
                "sticky": False,
            },
        }

    def action_view_logs_assignation(self):
        self.ensure_one()
        assignment_product_category = self._get_product_category_operator_assignment()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "product_asset.action_product_asset_log"
        )
        action["domain"] = [
            ("asset_id", "=", self.id),
            ("product_category_id", "=", assignment_product_category.id),
        ]
        action["context"] = {
            "default_asset_id": self.id,
            "default_operator_id": self.operator_id.id,
            "default_product_category_id": assignment_product_category.id,
        }
        return action

    # ------------------------------------------------------------
    # ASSIGNMENT MANAGEMENT METHODS
    # ------------------------------------------------------------

    def _create_assignment_log(
        self, old_operator=None, new_operator=None, change_type="manual"
    ):
        """Create a log entry for operator assignment changes

        Args:
            old_operator: Previous operator (hr.employee)
            new_operator: New operator (hr.employee)
            change_type: Type of change ('manual', 'scheduled', 'emergency')
        """
        self.ensure_one()

        # Build description
        description_parts = []
        if old_operator and new_operator:
            description_parts.append(
                f"Operator changed from {old_operator.name} to {new_operator.name}"
            )
        elif new_operator:
            description_parts.append(f"Operator assigned: {new_operator.name}")
        elif old_operator:
            description_parts.append(f"Operator removed: {old_operator.name}")

        if not description_parts:
            return False

        # Get default operator assignment product
        product = self._get_product_operator_assignment()

        # Create log entry
        log_vals = {
            "asset_id": self.id,
            "odometer": self.odometer,
            "date": fields.Date.today(),
            "operator_id": new_operator.id if new_operator else False,
            "product_id": product.id if product else False,
            "description": " ".join(description_parts),
            "state": "done",
        }

        return self.env["product.asset.log"].create(log_vals)

    def process_future_assignments(self):
        """Process all due future operator assignments

        This method should be called by a cron job to automatically
        process scheduled operator changes.
        """
        today = fields.Date.today()

        # Find all assets with due future assignments
        assets_to_process = self.search(
            [
                ("future_operator_id", "!=", False),
                ("date_next_assignation", "<=", today),
            ]
        )

        for asset in assets_to_process:
            try:
                # Store old operator for logging
                old_operator = asset.operator_id

                # Perform the assignment
                asset.operator_id = asset.future_operator_id

                # Clear future assignment fields
                asset.future_operator_id = False
                asset.date_next_assignation = False

                # Create assignment log
                asset._create_assignment_log(
                    old_operator=old_operator,
                    new_operator=asset.operator_id,
                    change_type="scheduled",
                )

                _logger.info(
                    f"Processed scheduled assignment for asset {asset.id}: "
                    f"{asset.operator_id.name if asset.operator_id else 'None'}"
                )

            except Exception as e:
                _logger.error(
                    f"Error processing future assignment for asset {asset.id}: {e}"
                )

    def accept_operator_change(self):
        """Accept the future operator assignment and update current operator

        This method:
        1. Removes current operator from other assets of same type
        2. Updates the operator_id with future_operator_id
        3. Creates assignment log
        4. Clears future assignment fields
        5. Shows confirmation message
        """
        for asset in self:
            if not asset.future_operator_id:
                raise models.UserError(
                    _("No future operator set. Please select a future operator first.")
                )

            # Store old operator for logging
            old_operator = asset.operator_id
            new_operator = asset.future_operator_id

            # Find other assets with the same operator and same type
            if new_operator:
                conflicting_assets = self.search(
                    [
                        ("operator_id", "=", new_operator.id),
                        ("asset_type", "=", asset.asset_type),
                        ("id", "!=", asset.id),
                    ]
                )

                # Remove operator from conflicting assets
                if conflicting_assets:
                    for conflicting in conflicting_assets:
                        conflicting._create_assignment_log(
                            old_operator=conflicting.operator_id,
                            new_operator=False,
                            change_type="reassignment",
                        )
                    conflicting_assets.write({"operator_id": False})

            # Update operator
            asset.operator_id = new_operator

            # Create assignment log
            asset._create_assignment_log(
                old_operator=old_operator,
                new_operator=new_operator,
                change_type="manual",
            )

            # Clear future assignment fields
            asset.future_operator_id = False
            asset.date_next_assignation = False

            # Send notification
            asset._notify_operator_change(old_operator, new_operator)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Assignment Completed"),
                "message": _("Operator assignment has been successfully updated."),
                "type": "success",
                "sticky": False,
            },
        }

    def get_assignment_history(self, limit=10):
        """Get assignment history for this asset

        Args:
            limit: Maximum number of records to return

        Returns:
            List of assignment log records
        """
        self.ensure_one()

        # Get operator assignment product to identify assignment logs
        product = self._get_product_operator_assignment()

        # Search for assignment logs
        domain = [("asset_id", "=", self.id)]
        if product:
            domain.append(("product_id", "=", product.id))

        assignments = self.env["product.asset.log"].search(
            domain, order="date desc", limit=limit
        )

        return assignments

    def _get_product_category_operator_assignment(self):
        product = self.env.ref(
            "product_asset.product_category_operator_assignment",
            raise_if_not_found=False,
        )
        return product or self.env["product.product"]

    def _get_product_operator_assignment(self):
        product = self.env.ref(
            "product_asset.product_product_operator_assignment",
            raise_if_not_found=False,
        )
        return product or self.env["product.product"]

    def get_operator_statistics(self):
        """Get statistics about operator assignments for this asset"""
        self.ensure_one()

        assignments = self.get_assignment_history(limit=None)

        # Calculate statistics
        stats = {
            "total_assignments": len(assignments),
            "current_operator": (
                self.operator_id.name if self.operator_id else _("Unassigned")
            ),
            "current_operator_since": False,
            "average_assignment_duration": 0,
            "operators": [],
        }

        if assignments:
            # Find when current operator was assigned
            for assignment in assignments:
                if assignment.operator_id == self.operator_id:
                    stats["current_operator_since"] = assignment.date
                    break

            # Calculate unique operators
            operators = assignments.mapped("operator_id")
            stats["operators"] = [
                {
                    "name": op.name,
                    "assignments": len(
                        assignments.filtered(lambda a: a.operator_id == op)
                    ),
                }
                for op in operators
            ]

        return stats

    # ------------------------------------------------------------
    # NOTIFICATION METHODS
    # ------------------------------------------------------------

    def _notify_operator_change(self, old_operator=None, new_operator=None):
        """Send notifications for operator changes

        Args:
            old_operator: Previous operator
            new_operator: New operator
        """
        # Prepare notification recipients
        partners_to_notify = self.env["res.partner"]

        if old_operator and old_operator.user_id:
            partners_to_notify |= old_operator.user_id.partner_id

        if new_operator and new_operator.user_id:
            partners_to_notify |= new_operator.user_id.partner_id

        if self.asset_manager_id and self.asset_manager_id.user_id:
            partners_to_notify |= self.asset_manager_id.user_id.partner_id

        if not partners_to_notify:
            return

        # Create notification message
        subject = _("Asset Assignment Change")
        body = _(
            "Asset %(asset)s assignment has been updated:<br/>"
            "Previous Operator: %(old_op)s<br/>"
            "New Operator: %(new_op)s<br/>"
            "Effective Date: %(date)s",
            asset=self.display_name,
            old_op=old_operator.name if old_operator else _("None"),
            new_op=new_operator.name if new_operator else _("None"),
            date=fields.Date.today(),
        )

        # Post message
        self.message_post(
            body=body,
            subject=subject,
            partner_ids=partners_to_notify.ids,
            message_type="notification",
            subtype_xmlid="mail.mt_note",
        )
