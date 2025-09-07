import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class AssetMixinService(models.AbstractModel):
    """Service and maintenance mixin for assets

    This mixin handles all service-related functionality:
    - Service scheduling and tracking
    - Maintenance history
    - Service alerts and reminders
    - Cost tracking for services
    """

    _name = "asset.mixin.service"
    _description = "Asset Service Mixin"

    # ------------------------------------------------------------
    # SERVICE FIELDS
    # ------------------------------------------------------------

    next_service_date = fields.Date(
        string="Next Service Date",
        help="Date when next service is due",
    )
    next_service_odometer = fields.Float(
        string="Next Service Odometer",
        help="Odometer reading when next service is due",
    )
    service_frequency_days = fields.Integer(
        string="Service Frequency (Days)",
        default=180,
        help="Number of days between regular services",
    )
    service_frequency_distance = fields.Float(
        string="Service Frequency (Distance)",
        default=10000,
        help="Distance between regular services",
    )
    last_service_date = fields.Date(
        string="Last Service Date",
        compute="_compute_last_service",
        store=True,
        help="Date of last completed service",
    )
    last_service_odometer = fields.Float(
        string="Last Service Odometer",
        compute="_compute_last_service",
        store=True,
        help="Odometer reading at last service",
    )
    service_overdue = fields.Boolean(
        string="Service Overdue",
        compute="_compute_service_status",
        store=True,
        help="Indicates if service is overdue",
    )
    days_until_service = fields.Integer(
        string="Days Until Service",
        compute="_compute_service_status",
        help="Number of days until next service",
    )

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    @api.depends("log_ids.state", "log_ids.date")
    def _compute_last_service(self):
        """Compute last service date and odometer"""
        # Get maintenance and repairs category
        try:
            service_category = self.env.ref(
                "product_asset.product_category_maintenance_and_repairs",
                False,
            )
        except Exception:
            service_category = False

        for asset in self:
            try:
                # Get completed service logs
                if service_category:
                    service_logs = asset.log_ids.filtered(
                        lambda l: l.product_category_id == service_category
                        and l.state == "done"
                    ).sorted("date", reverse=True)
                else:
                    service_logs = False

                if service_logs:
                    last_service = service_logs[0]
                    asset.last_service_date = last_service.date
                    asset.last_service_odometer = (
                        last_service.value if hasattr(last_service, "value") else 0
                    )
                else:
                    asset.last_service_date = False
                    asset.last_service_odometer = 0

            except Exception as e:
                _logger.warning(
                    f"Error computing last service for asset {asset.id}: {e}"
                )
                asset.last_service_date = False
                asset.last_service_odometer = 0

    @api.depends("next_service_date", "next_service_odometer", "odometer")
    def _compute_service_status(self):
        """Compute service status and days until service"""
        today = fields.Date.today()

        for asset in self:
            try:
                # Check date-based service
                date_overdue = False
                days_until = 0

                if asset.next_service_date:
                    days_until = (asset.next_service_date - today).days
                    date_overdue = asset.next_service_date < today

                # Check odometer-based service
                odometer_overdue = False
                if asset.next_service_odometer and hasattr(asset, "odometer"):
                    odometer_overdue = asset.odometer >= asset.next_service_odometer

                # Service is overdue if either condition is met
                asset.service_overdue = date_overdue or odometer_overdue
                asset.days_until_service = days_until

            except Exception as e:
                _logger.warning(
                    f"Error computing service status for asset {asset.id}: {e}"
                )
                asset.service_overdue = False
                asset.days_until_service = 0

    # ------------------------------------------------------------
    # SERVICE MANAGEMENT METHODS
    # ------------------------------------------------------------

    def schedule_next_service(self):
        """Schedule the next service based on frequency settings"""
        self.ensure_one()

        # Calculate next service date
        if self.service_frequency_days and self.last_service_date:
            from dateutil.relativedelta import relativedelta

            self.next_service_date = self.last_service_date + relativedelta(
                days=self.service_frequency_days
            )
        elif self.service_frequency_days:
            from dateutil.relativedelta import relativedelta

            self.next_service_date = fields.Date.today() + relativedelta(
                days=self.service_frequency_days
            )

        # Calculate next service odometer
        if self.service_frequency_distance and self.last_service_odometer:
            self.next_service_odometer = (
                self.last_service_odometer + self.service_frequency_distance
            )
        elif self.service_frequency_distance and hasattr(self, "odometer"):
            self.next_service_odometer = self.odometer + self.service_frequency_distance

    def create_service_log(self, service_data):
        """Create a service log entry

        Args:
            service_data: Dictionary containing service information
                - date: Service date
                - vendor_id: Service provider
                - amount: Service cost
                - description: Service description
                - odometer: Current odometer reading
                - product_id: Service product (optional)

        Returns:
            Created service log record
        """
        self.ensure_one()

        # Get default service product if not provided
        if not service_data.get("product_id"):
            product = self.env.ref(
                "product_asset.product_product_service", raise_if_not_found=False
            )
            service_data["product_id"] = product.id if product else False

        log_vals = {
            "asset_id": self.id,
            "product_id": service_data.get("product_id"),
            "date": service_data.get("date", fields.Date.today()),
            "vendor_id": service_data.get("vendor_id"),
            "amount": service_data.get("amount", 0.0),
            "description": service_data.get("description", _("Service")),
            "state": service_data.get("state", "done"),
        }

        # Add odometer if provided
        if "value" in self.env["product.asset.log"]._fields:
            log_vals["value"] = service_data.get("odometer", 0)

        return self.env["product.asset.log"].create(log_vals)

    def complete_service(self, service_log_id=None):
        """Mark a service as completed and schedule next service

        Args:
            service_log_id: ID of the service log to complete
        """
        self.ensure_one()

        if service_log_id:
            service_log = self.env["product.asset.log"].browse(service_log_id)
            service_log.state = "done"

        # Schedule next service
        self.schedule_next_service()

        # Send notification
        self._notify_service_completed()

    def get_service_history(self, limit=10):
        """Get service history for this asset

        Args:
            limit: Maximum number of services to return

        Returns:
            Recordset of service logs
        """
        self.ensure_one()

        # Get maintenance and repairs category
        try:
            service_category = self.env.ref(
                "product_asset.product_category_maintenance_and_repairs", False
            )
        except Exception:
            return self.env["product.asset.log"]

        if not service_category:
            return self.env["product.asset.log"]

        # Filter for service logs
        service_logs = self.log_ids.filtered(
            lambda l: l.product_category_id == service_category
        ).sorted("date", reverse=True)

        if limit:
            service_logs = service_logs[:limit]

        return service_logs

    def get_service_costs(self, date_from=None, date_to=None):
        """Calculate total service costs for the asset

        Args:
            date_from: Start date for cost calculation
            date_to: End date for cost calculation

        Returns:
            Dictionary with cost breakdown
        """
        self.ensure_one()

        # Get maintenance and repairs category
        try:
            service_category = self.env.ref(
                "product_asset.product_category_maintenance_and_repairs", False
            )
        except Exception:
            return {
                "total_cost": 0,
                "service_count": 0,
                "average_cost": 0,
                "costs_by_type": {},
            }

        if not service_category:
            return {
                "total_cost": 0,
                "service_count": 0,
                "average_cost": 0,
                "costs_by_type": {},
            }

        # Get service logs in date range
        domain = [
            ("asset_id", "=", self.id),
            ("state", "=", "done"),
            ("product_category_id", "=", service_category.id),
        ]

        if date_from:
            domain.append(("date", ">=", date_from))
        if date_to:
            domain.append(("date", "<=", date_to))

        service_logs = self.env["product.asset.log"].search(domain)

        # Calculate costs
        total_cost = sum(service_logs.mapped("amount"))
        service_count = len(service_logs)

        # Group by product if available
        costs_by_type = {}
        for product in service_logs.mapped("product_id"):
            product_logs = service_logs.filtered(lambda l: l.product_id == product)
            costs_by_type[product.name if product else _("Other")] = {
                "count": len(product_logs),
                "total": sum(product_logs.mapped("amount")),
            }

        return {
            "total_cost": total_cost,
            "service_count": service_count,
            "average_cost": total_cost / service_count if service_count else 0,
            "costs_by_type": costs_by_type,
        }

    def check_service_due(self):
        """Check all assets for due services

        This method should be called by a cron job to check
        for services that are due or overdue.
        """
        # Find assets with overdue services
        overdue_assets = self.search([("service_overdue", "=", True)])

        for asset in overdue_assets:
            asset._send_service_overdue_alert()

        # Find assets with services due soon (within 7 days)
        from dateutil.relativedelta import relativedelta

        due_soon_date = fields.Date.today() + relativedelta(days=7)

        due_soon_assets = self.search(
            [
                ("next_service_date", "<=", due_soon_date),
                ("next_service_date", ">", fields.Date.today()),
            ]
        )

        for asset in due_soon_assets:
            asset._send_service_reminder()

        _logger.info(
            f"Service check completed: {len(due_soon_assets)} due soon, "
            f"{len(overdue_assets)} overdue"
        )

    def _get_product_category_maintenance_and_repairs(self):
        product = self.env.ref(
            "product_asset.product_category_maintenance_and_repairs",
            raise_if_not_found=False,
        )
        return product or self.env["product.category"]

    def _get_product_maintenance(self):
        product = self.env.ref(
            "product_asset.product_product_maintenance",
            raise_if_not_found=False,
        )
        return product or self.env["product.product"]

    def _get_product_repair(self):
        product = self.env.ref(
            "product_asset.product_product_repair",
            raise_if_not_found=False,
        )
        return product or self.env["product.product"]

    # ------------------------------------------------------------
    # NOTIFICATION METHODS
    # ------------------------------------------------------------

    def _notify_service_completed(self):
        """Send notification when service is completed"""
        self.ensure_one()

        subject = _("Service Completed")
        body = _(
            "Service for asset %(asset)s has been completed.<br/>"
            "Service Date: %(date)s<br/>"
            "Next Service Due: %(next_date)s<br/>",
            asset=self.display_name,
            date=self.last_service_date or fields.Date.today(),
            next_date=self.next_service_date or _("Not scheduled"),
        )

        # Notify asset manager
        if self.asset_manager_id and self.asset_manager_id.user_id:
            self.message_post(
                body=body,
                subject=subject,
                partner_ids=[self.asset_manager_id.user_id.partner_id.id],
                message_type="notification",
                subtype_xmlid="mail.mt_note",
            )

    def _send_service_reminder(self):
        """Send service reminder notification"""
        self.ensure_one()

        subject = _("Service Reminder")
        body = _(
            "Service for asset %(asset)s is due soon.<br/>"
            "Next Service Date: %(date)s<br/>"
            "Days Until Service: %(days)s<br/>",
            asset=self.display_name,
            date=self.next_service_date,
            days=self.days_until_service,
        )

        # Notify asset manager and operator
        partners_to_notify = self.env["res.partner"]

        if self.asset_manager_id and self.asset_manager_id.user_id:
            partners_to_notify |= self.asset_manager_id.user_id.partner_id

        if (
            hasattr(self, "operator_id")
            and self.operator_id
            and self.operator_id.user_id
        ):
            partners_to_notify |= self.operator_id.user_id.partner_id

        if partners_to_notify:
            self.message_post(
                body=body,
                subject=subject,
                partner_ids=partners_to_notify.ids,
                message_type="notification",
                subtype_xmlid="mail.mt_note",
            )

    def _send_service_overdue_alert(self):
        """Send service overdue alert"""
        self.ensure_one()

        subject = _("⚠️ Service Overdue")

        overdue_info = []
        if self.next_service_date and self.next_service_date < fields.Date.today():
            days_overdue = (fields.Date.today() - self.next_service_date).days
            overdue_info.append(_("%(days)s days overdue", days=days_overdue))

        if (
            hasattr(self, "odometer")
            and self.next_service_odometer
            and self.odometer >= self.next_service_odometer
        ):
            distance_overdue = self.odometer - self.next_service_odometer
            overdue_info.append(
                _("%(distance).0f km over service interval", distance=distance_overdue)
            )

        body = _(
            "<strong>Service for asset %(asset)s is overdue!</strong><br/>"
            "Status: %(status)s<br/>"
            "Last Service: %(last_date)s<br/>"
            "<strong>Please schedule service immediately.</strong>",
            asset=self.display_name,
            status=" and ".join(overdue_info) if overdue_info else _("Overdue"),
            last_date=self.last_service_date or _("Never"),
        )

        # Notify with high priority
        partners_to_notify = self.env["res.partner"]

        if self.asset_manager_id and self.asset_manager_id.user_id:
            partners_to_notify |= self.asset_manager_id.user_id.partner_id

        if partners_to_notify:
            self.message_post(
                body=body,
                subject=subject,
                partner_ids=partners_to_notify.ids,
                message_type="notification",
                subtype_xmlid="mail.mt_comment",  # Higher visibility
            )
