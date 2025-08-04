import logging

from dateutil.relativedelta import relativedelta
from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import formatLang

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    """Inherit ResPartner"""

    _inherit = "res.partner"

    def _prepare_partner_category_domain(self):
        parents = []
        if self.env.user.has_group("account.group_account_basic"):
            parents.append(self.env.ref("marin.partner_category_management").id)
        if self.env.user.has_group("sales_team.group_sale_manager"):
            parents.append(self.env.ref("marin.partner_category_commercial").id)
        if self.env.user.has_group("marin.group_security_compliance"):
            parents.append(self.env.ref("marin.partner_category_security").id)
        if self.env.user.has_group("purchase.group_purchase_manager"):
            parents.append(self.env.ref("marin.partner_category_purchase").id)
        if not parents:
            return [("id", "=", False)]
        return [("parent_id", "!=", False), ("parent_id", "in", parents)]

    # Extend core fields
    category_id = fields.Many2many(domain=_prepare_partner_category_domain)

    # New fields
    mobile = fields.Char()

    # Security
    user_account_user = fields.Boolean(compute="_compute_group")
    user_debt_manager = fields.Boolean(compute="_compute_group")
    user_hr_user = fields.Boolean(compute="_compute_group")
    user_hr_manager = fields.Boolean(compute="_compute_group")
    user_purchase_manager = fields.Boolean(compute="_compute_group")
    user_sale_manager = fields.Boolean(compute="_compute_group")
    user_stock_user = fields.Boolean(compute="_compute_group")
    user_stock_manager = fields.Boolean(compute="_compute_group")

    # Accounting
    credit_limit_available = fields.Monetary(
        "Available Receivable Limit",
        compute="_compute_credit_limit_available",
        readonly=True,
        help="Available receivable limit",
    )

    # Misc
    customer = fields.Boolean()
    supplier = fields.Boolean()
    competitor = fields.Boolean()
    gender = fields.Selection(
        [("male", "Male"), ("female", "Female"), ("other", "Other")]
    )
    birthdate = fields.Date()
    age = fields.Integer(compute="_compute_age", readonly=True)
    age_range_id = fields.Many2one(
        "res.partner.age.range",
        "Age Range",
        compute="_compute_age_range_id",
        store=True,
    )
    b2x = fields.Selection(
        [
            ("b2b", "Business to business"),
            ("b2c", "Business to consumer"),
            ("both", "Business business and consumer"),
        ],
        default="b2c",
    )
    social_style_color = fields.Selection(
        [
            ("yellow", "yellow"),
            ("green", "green"),
            ("blue", "blue"),
            ("red", "red"),
        ],
        "Social style color",
    )
    team_id = fields.Many2one(
        "crm.team",
        "Sales Team",
        compute="_compute_team_id",
        store=True,
        precompute=True,  # avoid queries post-create
        readonly=False,
        ondelete="set null",
    )
    hectares = fields.Float(
        string="Hectares",
        default=0.0,
    )
    profile_id = fields.Many2one(
        "res.partner.profile",
        string="Assigned Profile",
        compute="_compute_partner_profile",
        store=True,
    )
    factor = fields.Float(
        string="Profile Factor",
        related="profile_id.factor",
        readonly=True,
    )

    # Customer merge fields
    auto_merge = fields.Boolean(
        string="Auto-merge when inactive",
        compute="_compute_auto_merge",
        store=True,
        readonly=False,
        help="If enabled, this customer will be automatically merged with the general public partner if they become inactive",
    )
    recent_orders_count = fields.Integer(
        string="Recent Orders Count",
        compute="_compute_recent_orders_count",
        help="Number of sale orders in the evaluation period",
    )
    days_since_last_order = fields.Integer(
        string="Days Since Last Order",
        compute="_compute_days_since_last_order",
        help="Number of days since the last sale order from this customer",
    )

    def _prepare_compute_group(self):
        return {
            "user_account_user": self.env.user.has_group("account.group_account_user"),
            "user_debt_manager": self.env.user.has_group(
                "marin.group_account_debt_manager"
            ),
            "user_hr_user": self.env.user.has_group("marin.group_hr_user"),
            "user_hr_manager": self.env.user.has_group("marin.group_hr_manager"),
            "user_purchase_manager": self.env.user.has_group(
                "purchase.group_purchase_manager"
            ),
            "user_sale_manager": self.env.user.has_group(
                "sales_team.group_sale_manager"
            ),
            "user_stock_user": self.env.user.has_group("marin.group_stock_user"),
            "user_stock_manager": self.env.user.has_group("marin.group_stock_manager"),
        }

    def _compute_group(self):
        for partner in self:
            vals = self._prepare_compute_group()
            partner.update(vals)

    @api.depends("parent_id")
    def _compute_team_id(self):
        for partner in self.filtered(
            lambda partner: not partner.team_id
            and partner.company_type == "person"
            and partner.parent_id.team_id
        ):
            partner.team_id = partner.parent_id.team_id

    @api.depends("birthdate")
    def _compute_age(self):
        for partner in self:
            partner.age = False
            if partner.birthdate:
                partner.age = relativedelta(
                    fields.Date.today(), partner.birthdate
                ).years

    @api.depends("age")
    def _compute_age_range_id(self):
        age_ranges = self.env["res.partner.age.range"].search([])
        for partner in self:
            if partner.age >= 0:
                age_range = age_ranges.filtered(
                    lambda age_range: age_range.age_from
                    <= partner.age
                    <= age_range.age_to
                )
            else:
                age_range = self.env["res.partner.age.range"].browse()
            if partner.age_range_id != age_range:
                partner.age_range_id = age_range

    @api.model
    def _cron_update_age_range_id(self):
        """This method is called from a cron job.
        It is used to update age range on contact
        """
        partners = self.search([("birthdate", "!=", False)])
        partners._compute_age_range_id()

    def _compute_credit_limit_available(self):
        for partner in self:
            partner.credit_limit_available = partner.credit_limit - partner.credit

    # New method inspired by the one in account.move
    def _build_credit_warning_message(self, future_credit, currency):
        msg = _(
            "The partner %s has reached its credit limit of : %s\n",
            self.name,
            formatLang(self.env, self.credit_limit, currency_obj=currency),
        )
        msg += _(
            "Total amount due (including this document): %s\n",
            formatLang(self.env, future_credit, currency_obj=currency),
        )
        msg += _(
            "Credit available: %s",
            formatLang(self.env, self.credit_limit_available, currency_obj=currency),
        )
        return msg

    # Override method to be like it was on v16 showing the partner ledger report
    # instead of showing the partner account move lines like it's done on v17.
    def open_partner_ledger(self):
        action = self.env["ir.actions.actions"]._for_xml_id(
            "account_reports.action_account_report_partner_ledger"
        )
        action["params"] = {
            "options": {"partner_ids": [self.id]},
            "ignore_session": "both",
        }
        return action

    @api.depends("category_id")
    def _compute_partner_profile(self):
        """Compute partner profile based on category matching."""
        for partner in self:
            if not partner.category_id:
                partner.profile_id = False
                continue

            partner_categories = set(partner.category_id.ids)
            profiles = self.env["res.partner.profile"].search([("active", "=", True)])
            if not profiles:
                partner.profile_id = False
                continue

            best_profile = False
            max_matches = 0
            min_sequence = max(profiles.mapped("sequence"))

            for profile in profiles:
                profile_categories = set(profile.category_ids.ids)
                matches = len(partner_categories & profile_categories)

                if matches > max_matches or (
                    matches == max_matches and profile.sequence < min_sequence
                ):
                    max_matches = matches
                    min_sequence = profile.sequence
                    best_profile = profile

            partner.profile_id = best_profile if max_matches > 0 else False

    @api.constrains("hectares")
    def _check_hectares_positive(self):
        """Ensure hectares is not negative."""
        for partner in self:
            if partner.hectares < 0:
                raise ValidationError(_("Hectares cannot be negative."))

    @api.depends("customer")
    def _compute_auto_merge(self):
        """Compute auto_merge based on customer flag and global configuration"""
        config_active = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("customer_merge_active", False)
        )
        for partner in self:
            if partner.customer and config_active:
                partner.auto_merge = True
            else:
                partner.auto_merge = False

    def _compute_recent_orders_count(self):
        """Compute number of sale orders in the evaluation period"""
        config = self.env["ir.config_parameter"].sudo()
        interval_number = int(config.get_param("customer_merge_interval_number", 3))
        interval_type = config.get_param("customer_merge_interval_type", "months")

        # Calculate cutoff date
        if interval_type == "days":
            cutoff_date = fields.Date.today() - relativedelta(days=interval_number)
        elif interval_type == "weeks":
            cutoff_date = fields.Date.today() - relativedelta(weeks=interval_number)
        else:  # months
            cutoff_date = fields.Date.today() - relativedelta(months=interval_number)

        for partner in self:
            if not partner.customer:
                partner.recent_orders_count = 0
                continue

            # Count confirmed sale orders in the period
            order_count = self.env["sale.order"].search_count(
                [
                    ("partner_id", "=", partner.id),
                    ("state", "=", "sale"),
                    ("date_order", ">=", cutoff_date),
                ]
            )
            partner.recent_orders_count = order_count

    def _compute_days_since_last_order(self):
        """Compute days since last sale order"""
        for partner in self:
            if not partner.customer:
                partner.days_since_last_order = 0
                continue

            last_order = self.env["sale.order"].search(
                [("partner_id", "=", partner.id), ("state", "=", "sale")],
                order="date_order desc",
                limit=1,
            )

            if last_order:
                delta = fields.Date.today() - last_order.date_order.date()
                partner.days_since_last_order = delta.days
            else:
                partner.days_since_last_order = 9999  # No orders found

    def _find_merge_candidates(self):
        """Find customers that are candidates for merging with general public"""
        config = self.env["ir.config_parameter"].sudo()

        min_orders = int(config.get_param("customer_merge_min_orders", 2))
        general_partner_id = int(
            config.get_param("customer_merge_general_partner_id", 0)
        )

        # Get evaluation period settings
        interval_number = int(config.get_param("customer_merge_interval_number", 3))
        interval_type = config.get_param("customer_merge_interval_type", "months")

        if not general_partner_id:
            _logger.warning("No general partner configured for customer merge")
            return self.env["res.partner"]

        # Calculate minimum creation date (same as evaluation period)
        # Only consider partners created before this cutoff to give them time to fulfill requirements
        if interval_type == "days":
            min_creation_date = fields.Date.today() - relativedelta(
                days=interval_number
            )
        elif interval_type == "weeks":
            min_creation_date = fields.Date.today() - relativedelta(
                weeks=interval_number
            )
        else:  # months
            min_creation_date = fields.Date.today() - relativedelta(
                months=interval_number
            )

        # Get required fields from company_lmmr configuration
        try:
            company = self.env.ref("marin_data.company_lmmr")
        except ValueError:
            company = self.env.company  # Fallback to default company
        required_fields = company.customer_merge_required_fields.mapped("name")

        candidates = self.env["res.partner"]

        # Search for customers with auto_merge enabled
        partners = self.search(
            [
                ("customer", "=", True),
                ("auto_merge", "=", True),
                ("id", "!=", general_partner_id),
            ]
        )

        for partner in partners:
            # Check if required fields are completed (immediate merge regardless of creation date)
            missing_fields = []
            for field_name in required_fields:
                if hasattr(partner, field_name):
                    field_value = getattr(partner, field_name)
                    if not field_value:
                        missing_fields.append(field_name)

            if missing_fields:
                _logger.info(
                    f"Partner {partner.name} (ID: {partner.id}) is a merge candidate - missing fields: {missing_fields}"
                )
                candidates |= partner
            elif (
                partner.create_date.date() <= min_creation_date
                and partner.recent_orders_count < min_orders
            ):
                # Only check order activity for partners old enough to have had time to place orders
                _logger.info(
                    f"Partner {partner.name} (ID: {partner.id}) is a merge candidate - insufficient orders: {partner.recent_orders_count}"
                )
                candidates |= partner

        return candidates

    def _merge_family_hierarchy(self, parent_partner):
        """Merge all children and grandchildren into the parent partner

        This method breaks parent-child relationships first to avoid merge restrictions,
        then merges all family members into the parent partner.
        """
        if not parent_partner.child_ids:
            return  # No children to merge

        # Collect all descendants recursively (children, grandchildren, etc.)
        all_descendants = self._get_all_descendants(parent_partner)

        if not all_descendants:
            return

        # Break all parent-child relationships first to avoid merge restrictions
        all_descendants.write({"parent_id": False})

        # Now merge all descendants with parent in batches of 2
        batch_size = 2  # Max 2 descendants + 1 parent = 3 total

        for i in range(0, len(all_descendants), batch_size):
            batch = all_descendants[i : i + batch_size]
            if batch:
                try:
                    # Standard merge (no cleanup context) to preserve descendant data in parent
                    child_wizard = self.env[
                        "base.partner.merge.automatic.wizard"
                    ].create({})
                    all_family = batch | parent_partner
                    child_wizard._merge(
                        all_family.ids, dst_partner=parent_partner, extra_checks=False
                    )
                except Exception as e:
                    _logger.error(
                        f"Error merging descendants {batch.ids} with parent {parent_partner.id}: {str(e)}"
                    )

    def _get_all_descendants(self, parent_partner):
        """Recursively get all descendants (children, grandchildren, etc.)"""
        descendants = self.env["res.partner"]

        def collect_children(partner):
            nonlocal descendants
            children = partner.child_ids
            descendants |= children
            for child in children:
                collect_children(child)

        collect_children(parent_partner)
        return descendants

    def _merge_with_general_partner(self, partner_ids):
        """Helper method to merge partners with the general public partner"""
        config = self.env["ir.config_parameter"].sudo()
        general_partner_id = int(
            config.get_param("customer_merge_general_partner_id", 0)
        )
        general_partner = self.env["res.partner"].browse(general_partner_id)

        partners_to_merge = self.browse(partner_ids)
        if not partners_to_merge:
            return False

        try:
            # First, recursively merge all family hierarchies into their root parents
            for partner in partners_to_merge:
                self._merge_family_hierarchy(partner)

            # Use the base partner merge wizard with context to prevent field value merging
            wizard = (
                self.env["base.partner.merge.automatic.wizard"]
                .with_context(customer_merge_cleanup=True)
                .create({})
            )

            # Store original general partner categories before merge
            original_categories = general_partner.category_id

            # Add general partner to the list
            all_partners = partners_to_merge | general_partner

            # Perform the merge
            wizard._merge(
                all_partners.ids, dst_partner=general_partner, extra_checks=False
            )

            # Restore original categories to preserve general partner's identity
            general_partner.write(
                {"category_id": [Command.set(original_categories.ids)]}
            )

            return True

        except Exception as e:
            _logger.error(
                f"Error merging partners {partner_ids} with general partner: {str(e)}"
            )
            return False

    @api.model
    def _cron_merge_inactive_customers(self):
        """Cron job to merge inactive customers with general public partner"""
        config = self.env["ir.config_parameter"].sudo()
        if not config.get_param("customer_merge_active"):
            return

        _logger.info("Starting automatic customer merge process")

        candidates = self._find_merge_candidates()
        if not candidates:
            _logger.info("No merge candidates found")
            return

        _logger.info(
            f"Found {len(candidates)} merge candidates: {candidates.mapped('name')}"
        )

        # Merge candidates in batches (max 2 candidates + 1 general partner = 3 total)
        batch_size = 2  # Maximum 2 candidates per batch due to wizard limit
        for i in range(0, len(candidates), batch_size):
            batch = candidates[i : i + batch_size]
            self._merge_with_general_partner(batch.ids)
            self.env.cr.commit()  # Commit each batch

        _logger.info("Completed automatic customer merge process")

    def _validate_restricted_contact_fields(self, vals=None):
        """
        Validate that all mandatory fields are completed for restricted contact creation.

        Args:
            vals: Dictionary of values to be written (for write method)

        Raises:
            ValidationError: If mandatory fields are missing
        """
        # Check if restricted contact creation is enabled
        config = self.env["ir.config_parameter"].sudo()
        if not config.get_param("sale.restricted_contact_creation", False):
            return True

        # Check if user belongs to restricted group
        if not self.env.user.has_group("marin.group_partner_restricted"):
            return True

        # Get required fields from company configuration with sudo
        company = self.env.company
        required_fields = company.sudo().restricted_contact_required_fields

        if not required_fields:
            return True

        missing_fields = []

        # For create method
        if vals is not None and not self:
            for field in required_fields.sudo():
                field_name = field.name
                field_value = vals.get(field_name)

                # Check if field is empty
                if not field_value or (
                    isinstance(field_value, str) and not field_value.strip()
                ):
                    missing_fields.append(field.field_description)

        # For write method or checking existing record
        else:
            for record in self:
                for field in required_fields.sudo():
                    field_name = field.name

                    # Get the value from vals if provided, otherwise from the record
                    if vals and field_name in vals:
                        field_value = vals[field_name]
                    else:
                        field_value = record[field_name]

                    # Check if field is empty
                    if field.ttype in ["many2one"]:
                        if not field_value or (
                            hasattr(field_value, "id") and not field_value.id
                        ):
                            missing_fields.append(field.field_description)
                    elif field.ttype in ["many2many", "one2many"]:
                        if not field_value or (
                            hasattr(field_value, "ids") and not field_value.ids
                        ):
                            missing_fields.append(field.field_description)
                    elif not field_value or (
                        isinstance(field_value, str) and not field_value.strip()
                    ):
                        missing_fields.append(field.field_description)

        if missing_fields:
            missing_fields = list(set(missing_fields))  # Remove duplicates
            raise ValidationError(
                _(
                    "Cannot save contact. The following mandatory fields must be completed:\n• %s"
                )
                % "\n• ".join(missing_fields)
            )

        return True

    @api.model_create_multi
    def create(self, vals_list):
        """
        Override create to validate mandatory fields for restricted users.
        """
        for vals in vals_list:
            # Only validate if it's a company or standalone contact (not a child contact)
            if not vals.get("parent_id"):
                self._validate_restricted_contact_fields(vals)

        return super().create(vals_list)

    def write(self, vals):
        """
        Override write to validate mandatory fields for restricted users.
        """
        # Only validate for company or standalone contacts (not child contacts)
        for record in self:
            if not record.parent_id:
                record._validate_restricted_contact_fields(vals)

        return super().write(vals)

    def action_generate_sale_targets(self):
        """Open wizard to generate sale targets for selected partners."""
        if not self:
            raise UserError(_("Please select at least one customer."))

        partners = self.filtered(lambda p: p.is_company and p.customer)
        if not partners:
            raise UserError(
                _("Please select customers (companies with customer flag enabled).")
            )

        return {
            "name": _("Generate Sale Targets"),
            "type": "ir.actions.act_window",
            "res_model": "sale.target.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_partner_ids": [(6, 0, partners.ids)],
                "default_date_from": fields.Date.today(),
            },
        }
