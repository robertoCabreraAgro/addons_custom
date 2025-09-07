import logging

from odoo import api, fields, models, _
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)


class AssetMixinContract(models.AbstractModel):
    """Contract management mixin for assets

    This mixin handles all contract-related functionality:
    - Contract tracking and states
    - Renewal reminders and alerts
    - Contract expiry management
    - Contract history
    """

    _name = "asset.mixin.contract"
    _description = "Asset Contract Mixin"

    # ------------------------------------------------------------
    # CONTRACT FIELDS
    # ------------------------------------------------------------

    contract_renewal_due_soon = fields.Boolean(
        string="Contract Renewal Due Soon",
        compute="_compute_contract_reminder",
        compute_sudo=False,
        store=True,
        search="_search_contract_renewal_due_soon",
        help="Indicates if any contract needs renewal soon",
    )
    contract_renewal_overdue = fields.Boolean(
        string="Contract Renewal Overdue",
        compute="_compute_contract_reminder",
        compute_sudo=False,
        store=True,
        search="_search_get_overdue_contract_reminder",
        help="Indicates if any contract renewal is overdue",
    )
    contract_state = fields.Selection(
        selection=[
            ("futur", "Incoming"),
            ("open", "In Progress"),
            ("expired", "Expired"),
            ("closed", "Closed"),
        ],
        string="Contract State",
        required=False,
        compute="_compute_contract_reminder",
        compute_sudo=False,
        store=True,
        help="Current state of the active contract",
    )
    contract_renewal_date = fields.Date(
        string="Contract Renewal Date",
        help="Next contract renewal date",
    )
    contract_renewal_reminder_days = fields.Integer(
        string="Renewal Reminder (days)",
        default=30,
        help="Number of days before renewal to send reminder",
    )

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    @api.depends("log_ids.state", "log_ids.date_end")
    def _compute_contract_reminder(self):
        """Compute contract renewal status and reminders"""
        # Get insurance and policies category
        try:
            contract_category = self.env.ref(
                "product_asset.product_category_insurance_and_policies", False
            )
        except Exception:
            contract_category = False

        if not contract_category:
            for asset in self:
                asset.contract_renewal_due_soon = False
                asset.contract_renewal_overdue = False
                asset.contract_state = "closed"
            return

        for asset in self:
            try:
                # Get all contract logs (insurance and policies category)
                contract_logs = asset.log_ids.filtered(
                    lambda log: log.product_category_id == contract_category
                )

                # Find active contracts (not closed/cancelled)
                active_contracts = contract_logs.filtered(
                    lambda c: c.state not in ["done", "cancelled"]
                )

                if not active_contracts:
                    asset.contract_renewal_due_soon = False
                    asset.contract_renewal_overdue = False
                    asset.contract_state = "closed"
                    continue

                # Get the contract with nearest expiration
                upcoming_contract = (
                    active_contracts.sorted("date_end")[0]
                    if active_contracts
                    else False
                )

                if upcoming_contract and upcoming_contract.date_end:
                    today = fields.Date.today()
                    expiration = upcoming_contract.date_end
                    reminder_date = expiration - relativedelta(
                        days=asset.contract_renewal_reminder_days
                    )

                    # Set renewal status
                    asset.contract_renewal_overdue = expiration < today
                    asset.contract_renewal_due_soon = (
                        reminder_date <= today <= expiration
                    ) and not asset.contract_renewal_overdue

                    # Set contract state
                    if expiration < today:
                        asset.contract_state = "expired"
                    elif upcoming_contract.state == "futur":
                        asset.contract_state = "futur"
                    else:
                        asset.contract_state = "open"
                else:
                    asset.contract_renewal_due_soon = False
                    asset.contract_renewal_overdue = False
                    asset.contract_state = "closed"

            except Exception as e:
                _logger.warning(
                    f"Error computing contract reminder for asset {asset.id}: {e}"
                )
                asset.contract_renewal_due_soon = False
                asset.contract_renewal_overdue = False
                asset.contract_state = False

    # ------------------------------------------------------------
    # SEARCH METHODS
    # ------------------------------------------------------------

    def _search_contract_renewal_due_soon(self, operator, value):
        """Search for assets with contracts due for renewal soon"""
        today = fields.Date.today()

        # Get insurance and policies category
        try:
            contract_category = self.env.ref(
                "product_asset.product_category_insurance_and_policies", False
            )
        except Exception:
            return []

        if not contract_category:
            return []

        # Find all assets with contract logs
        assets_with_contracts = (
            self.env["product.asset.log"]
            .search(
                [
                    ("product_category_id", "=", contract_category.id),
                    ("state", "not in", ["done", "cancelled"]),
                    ("date_end", "!=", False),
                ]
            )
            .mapped("asset_id")
        )

        due_soon_ids = []
        for asset in assets_with_contracts:
            contract_logs = asset.log_ids.filtered(
                lambda l: l.product_category_id == contract_category
                and l.state not in ["done", "cancelled"]
                and l.date_end
            )

            if contract_logs:
                nearest = contract_logs.sorted("date_end")[0]
                reminder_date = nearest.date_end - relativedelta(
                    days=asset.contract_renewal_reminder_days
                )

                if reminder_date <= today <= nearest.date_end:
                    due_soon_ids.append(asset.id)

        if operator == "=" and value or operator == "!=" and not value:
            return [("id", "in", due_soon_ids)]
        else:
            return [("id", "not in", due_soon_ids)]

    def _search_get_overdue_contract_reminder(self, operator, value):
        """Search for assets with overdue contract renewals"""
        today = fields.Date.today()

        # Get insurance and policies category
        try:
            contract_category = self.env.ref(
                "product_asset.product_category_insurance_and_policies",
                False,
            )
        except Exception:
            return []

        if not contract_category:
            return []

        # Find all assets with expired contracts
        expired_contracts = self.env["product.asset.log"].search(
            [
                ("product_category_id", "=", contract_category.id),
                ("state", "not in", ["done", "cancelled"]),
                ("date_end", "<", today),
            ]
        )

        overdue_asset_ids = expired_contracts.mapped("asset_id").ids

        if operator == "=" and value or operator == "!=" and not value:
            return [("id", "in", overdue_asset_ids)]
        else:
            return [("id", "not in", overdue_asset_ids)]

    # ------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------

    def action_view_logs_contract(self):
        """
        This opens the xml view specified in xml_id for the current vehicle (contracts)
        """
        self.ensure_one()
        contract_product_category = self._get_product_category_contract()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "product_asset.action_product_asset_log"
        )
        action["domain"] = [
            ("asset_id", "=", self.id),
            ("product_category_id", "=", contract_product_category.id),
        ]
        action["context"] = {
            "default_asset_id": self.id,
            "default_product_category_id": contract_product_category.id,
        }
        return action

    # ------------------------------------------------------------
    # CONTRACT MANAGEMENT METHODS
    # ------------------------------------------------------------

    def create_contract(self, contract_data):
        """Create a new contract for this asset

        Args:
            contract_data: Dictionary containing contract information
                - vendor_id: Contract vendor
                - date: Contract start date
                - date_end: Contract end date
                - amount: Contract amount
                - description: Contract description
                - product_id: Contract product (optional)

        Returns:
            Created contract log record
        """
        self.ensure_one()

        # Get default insurance product if not provided
        if not contract_data.get("product_id"):
            product = self.env.ref(
                "product_asset.product_product_insurance", raise_if_not_found=False
            )
            contract_data["product_id"] = product.id if product else False

        log_vals = {
            "asset_id": self.id,
            "product_id": contract_data.get("product_id"),
            "date": contract_data.get("date", fields.Date.today()),
            "date_end": contract_data.get("date_end"),
            "vendor_id": contract_data.get("vendor_id"),
            "amount": contract_data.get("amount", 0.0),
            "description": contract_data.get("description", _("New Contract")),
            "state": (
                "running"
                if contract_data.get("date", fields.Date.today()) <= fields.Date.today()
                else "futur"
            ),
        }

        return self.env["product.asset.log"].create(log_vals)

    def renew_contract(self, contract_id, renewal_data):
        """Renew an existing contract

        Args:
            contract_id: ID of the contract to renew
            renewal_data: Dictionary with renewal information

        Returns:
            New contract log record
        """
        self.ensure_one()

        old_contract = self.env["product.asset.log"].browse(contract_id)

        if not old_contract or old_contract.asset_id != self:
            return False

        # Mark old contract as done
        old_contract.state = "done"

        # Create new contract
        new_contract_data = {
            "vendor_id": renewal_data.get("vendor_id", old_contract.vendor_id.id),
            "date": renewal_data.get("date", fields.Date.today()),
            "date_end": renewal_data.get("date_end"),
            "amount": renewal_data.get("amount", old_contract.amount),
            "description": renewal_data.get(
                "description", f"Renewal of {old_contract.description}"
            ),
        }

        return self.create_contract(new_contract_data)

    def get_active_contracts(self):
        """Get all active contracts for this asset

        Returns:
            Recordset of active contract logs
        """
        self.ensure_one()

        # Get insurance and policies category
        try:
            contract_category = self.env.ref(
                "product_asset.product_category_insurance_and_policies", False
            )
        except Exception:
            return self.env["product.asset.log"]

        if not contract_category:
            return self.env["product.asset.log"]

        return self.log_ids.filtered(
            lambda l: l.product_category_id == contract_category
            and l.state in ["running", "futur"]
        )

    def get_contract_history(self, limit=10):
        """Get contract history for this asset

        Args:
            limit: Maximum number of contracts to return

        Returns:
            Recordset of contract logs
        """
        self.ensure_one()

        # Get insurance and policies category
        try:
            contract_category = self.env.ref(
                "product_asset.product_category_insurance_and_policies", False
            )
        except Exception:
            return self.env["product.asset.log"]

        if not contract_category:
            return self.env["product.asset.log"]

        contracts = self.log_ids.filtered(
            lambda l: l.product_category_id == contract_category
        ).sorted("date", reverse=True)

        if limit:
            contracts = contracts[:limit]

        return contracts

    def check_contracts_to_renew(self):
        """Check all assets for contracts that need renewal

        This method should be called by a cron job to check
        for contracts needing renewal and send notifications.
        """
        # Find all assets with contracts due soon
        assets_due_soon = self.search([("contract_renewal_due_soon", "=", True)])

        for asset in assets_due_soon:
            asset._send_contract_renewal_reminder()

        # Find all assets with overdue contracts
        assets_overdue = self.search([("contract_renewal_overdue", "=", True)])

        for asset in assets_overdue:
            asset._send_contract_overdue_alert()

        _logger.info(
            f"Contract check completed: {len(assets_due_soon)} due soon, "
            f"{len(assets_overdue)} overdue"
        )

    def _get_product_category_contract(self):
        product = self.env.ref(
            "product_asset.product_category_insurance_and_policies",
            raise_if_not_found=False,
        )
        return product or self.env["product.product"]

    def _get_product_contract(self):
        product = self.env.ref(
            "product_asset.product_product_insurance",
            raise_if_not_found=False,
        )
        return product or self.env["product.product"]

    # ------------------------------------------------------------
    # NOTIFICATION METHODS
    # ------------------------------------------------------------

    def _send_contract_renewal_reminder(self):
        """Send contract renewal reminder notification"""
        self.ensure_one()

        # Get the contract that needs renewal
        active_contracts = self.get_active_contracts()
        if not active_contracts:
            return

        contract = active_contracts.sorted("date_end")[0]

        # Prepare notification
        subject = _("Contract Renewal Reminder")
        body = _(
            "The contract for asset %(asset)s will expire on %(date)s.<br/>"
            "Vendor: %(vendor)s<br/>"
            "Contract: %(contract)s<br/>"
            "Please arrange for renewal.",
            asset=self.display_name,
            date=contract.date_end,
            vendor=contract.vendor_id.name if contract.vendor_id else _("N/A"),
            contract=contract.description,
        )

        # Send to asset manager
        partners_to_notify = self.env["res.partner"]
        if self.asset_manager_id and self.asset_manager_id.user_id:
            partners_to_notify |= self.asset_manager_id.user_id.partner_id

        if partners_to_notify:
            self.message_post(
                body=body,
                subject=subject,
                partner_ids=partners_to_notify.ids,
                message_type="notification",
                subtype_xmlid="mail.mt_note",
            )

    def _send_contract_overdue_alert(self):
        """Send contract overdue alert"""
        self.ensure_one()

        # Get insurance and policies category
        try:
            contract_category = self.env.ref(
                "product_asset.product_category_insurance_and_policies", False
            )
        except Exception:
            return

        if not contract_category:
            return

        # Get overdue contracts
        overdue_contracts = self.log_ids.filtered(
            lambda l: l.product_category_id == contract_category
            and l.date_end
            and l.date_end < fields.Date.today()
            and l.state not in ["done", "cancelled"]
        )

        if not overdue_contracts:
            return

        for contract in overdue_contracts:
            days_overdue = (fields.Date.today() - contract.date_end).days

            subject = _("⚠️ Contract Overdue Alert")
            body = _(
                "<strong>Contract for asset %(asset)s is %(days)s days overdue!</strong><br/>"
                "Expired Date: %(date)s<br/>"
                "Vendor: %(vendor)s<br/>"
                "Contract: %(contract)s<br/>"
                "<strong>Immediate action required.</strong>",
                asset=self.display_name,
                days=days_overdue,
                date=contract.date_end,
                vendor=contract.vendor_id.name if contract.vendor_id else _("N/A"),
                contract=contract.description,
            )

            # Send to asset manager with high priority
            partners_to_notify = self.env["res.partner"]
            if self.asset_manager_id and self.asset_manager_id.user_id:
                partners_to_notify |= self.asset_manager_id.user_id.partner_id

            if partners_to_notify:
                self.message_post(
                    body=body,
                    subject=subject,
                    partner_ids=partners_to_notify.ids,
                    message_type="notification",
                    subtype_xmlid="mail.mt_comment",  # Use comment for higher visibility
                )
