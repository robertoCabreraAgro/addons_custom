from odoo import api, fields, models


class ResCompany(models.Model):
    """Extend company with purchase approval settings."""
    _inherit = "res.company"

    # ============================================================================
    # FIELDS
    # ============================================================================

    # Purchase Approval Configuration
    purchase_approval_limit = fields.Monetary(
        string="Purchase Approval Limit",
        default=0.0,
        help="Purchase orders above this amount require approval. Set to 0 to disable approval."
    )

    default_approval_category_id = fields.Many2one(
        "approval.category.purchase",
        string="Default Approval Category",
        help="Default approval category for purchase orders"
    )

    auto_create_approval_requests = fields.Boolean(
        string="Auto Create Approval Requests",
        default=True,
        help="Automatically create approval requests when confirming purchase orders"
    )

    approval_required_for_vendors = fields.Many2many(
        "res.partner",
        "company_approval_vendor_rel",
        "company_id", "partner_id",
        string="Vendors Requiring Approval",
        domain="[('supplier_rank', '>', 0)]",
        help="Vendors that always require approval regardless of amount"
    )

    approval_exempt_users = fields.Many2many(
        "res.users",
        "company_approval_exempt_user_rel",
        "company_id", "user_id",
        string="Users Exempt from Approval",
        domain="[('share', '=', False)]",
        help="Users who can confirm purchase orders without approval"
    )

    # Notification Settings
    notify_approval_required = fields.Boolean(
        string="Notify When Approval Required",
        default=True,
        help="Send notification when a purchase order requires approval"
    )

    approval_notification_template_id = fields.Many2one(
        "mail.template",
        string="Approval Notification Template",
        domain="[('model_id.model', '=', 'approval.request.purchase')]",
        help="Email template for approval notifications"
    )

    # ============================================================================
    # METHODS
    # ============================================================================

    def get_purchase_approval_category(self, amount, partner=None, products=None):
        """Get the appropriate approval category for a purchase.

        Args:
            amount (float): Purchase amount
            partner (res.partner): Vendor partner
            products (list): List of products

        Returns:
            approval.category.purchase: Appropriate category or False
        """
        self.ensure_one()

        if amount <= 0:
            return False

        # Check if approval is required based on amount
        if self.purchase_approval_limit > 0 and amount <= self.purchase_approval_limit:
            return False

        # Find category based on amount and restrictions
        categories = self.env["approval.category.purchase"].search([
            ("company_id", "=", self.id),
            ("active", "=", True),
            "|", ("minimum_amount", "<=", amount), ("minimum_amount", "=", 0),
            "|", ("maximum_amount", ">=", amount), ("maximum_amount", "=", 0)
        ])

        # Filter by partner restrictions
        if partner and categories:
            valid_categories = []
            for category in categories:
                if category.validate_partner(partner)[0]:
                    valid_categories.append(category)
            categories = self.env["approval.category.purchase"].browse([c.id for c in valid_categories])

        # Filter by product restrictions
        if products and categories:
            valid_categories = []
            for category in categories:
                if category.validate_products(products)[0]:
                    valid_categories.append(category)
            categories = self.env["approval.category.purchase"].browse([c.id for c in valid_categories])

        # Return first matching category or default
        if categories:
            return categories[0]

        return self.default_approval_category_id

    def is_approval_required(self, amount, partner=None, user=None):
        """Check if approval is required for a purchase.

        Args:
            amount (float): Purchase amount
            partner (res.partner): Vendor partner
            user (res.users): User making the purchase

        Returns:
            bool: True if approval is required
        """
        self.ensure_one()

        # Check if user is exempt
        if user and user in self.approval_exempt_users:
            return False

        # Check amount threshold
        if self.purchase_approval_limit > 0 and amount > self.purchase_approval_limit:
            return True

        # Check vendor requirements
        if partner and partner in self.approval_required_for_vendors:
            return True

        return False

    @api.model
    def _get_approval_settings(self, company_id=None):
        """Get approval settings for a company.

        Args:
            company_id (int): Company ID (default: current company)

        Returns:
            dict: Approval settings
        """
        if not company_id:
            company_id = self.env.company.id

        company = self.browse(company_id)

        return {
            "approval_limit": company.purchase_approval_limit,
            "auto_create_requests": company.auto_create_approval_requests,
            "default_category_id": company.default_approval_category_id.id,
            "notify_approval_required": company.notify_approval_required,
            "approval_required_vendors": company.approval_required_for_vendors.ids,
            "approval_exempt_users": company.approval_exempt_users.ids,
        }