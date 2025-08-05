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
    
    score_hectares = fields.Float(
        string='Hectares Score',
        compute='_compute_client_score',
        store=True,
    )
    score_categories = fields.Float(
        string='Categories Score',
        compute='_compute_client_score',
        store=True,
    )
    score_total = fields.Float(
        string='Total Score',
        compute='_compute_client_score',
        store=True,
    )
    
    profile_history_ids = fields.One2many(
        'res.partner.profile.history',
        'partner_id',
        string='Profile History',
    )
    profile_change_count = fields.Integer(
        string='Profile Changes',
        compute='_compute_profile_stats',
    )
    last_profile_change = fields.Date(
        string='Last Profile Change',
        compute='_compute_profile_stats',
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

    @api.depends('category_id', 'hectares', 'score_total')
    def _compute_partner_profile(self):
        """Compute partner profile based on dynamic scoring system."""
        for partner in self:
            old_profile = partner.profile_id
            old_score = partner.score_total or 0
            
            new_profile = self.env['res.partner.profile'].search([
                ('score_min', '<=', partner.score_total),
                ('score_max', '>=', partner.score_total),
                ('active', '=', True)
            ], order='sequence', limit=1)
            
            if not new_profile:
                new_profile = self._fallback_profile_matching(partner)
            
            partner.profile_id = new_profile
            
            if (partner.id and old_profile and new_profile and old_profile != new_profile):
                self._create_profile_history_record(partner, old_profile, new_profile, old_score)
    
    def _fallback_profile_matching(self, partner):
        """Fallback profile matching based on category overlap."""
        if not partner.category_id:
            return False
            
        partner_categories = set(partner.category_id.ids)
        profiles = self.env['res.partner.profile'].search([('active', '=', True)])
        
        best_profile = False
        max_matches = 0
        min_sequence = float('inf')
        
        for profile in profiles:
            profile_categories = set(profile.category_ids.ids)
            matches = len(partner_categories & profile_categories)
            
            if (matches > max_matches or 
                (matches == max_matches and profile.sequence < min_sequence)):
                max_matches = matches
                min_sequence = profile.sequence
                best_profile = profile
        
        return best_profile if max_matches > 0 else False
    
    def _create_profile_history_record(self, partner, old_profile, new_profile, old_score):
        """Create profile history record for tracking changes."""
        change_trigger = 'manual'
        reason_parts = []
        
        if hasattr(partner, '_origin') and partner._origin.hectares != partner.hectares:
            change_trigger = 'hectares'
            reason_parts.append(f"Hectares: {partner._origin.hectares} → {partner.hectares}")
        
        if hasattr(partner, '_origin'):
            old_cats = (set(partner._origin.category_id.mapped('name')) 
                       if partner._origin.category_id else set())
            new_cats = (set(partner.category_id.mapped('name')) 
                       if partner.category_id else set())
            
            if old_cats != new_cats:
                change_trigger = 'category'
                added = new_cats - old_cats
                removed = old_cats - new_cats
                if added:
                    reason_parts.append(f"Added: {', '.join(added)}")
                if removed:
                    reason_parts.append(f"Removed: {', '.join(removed)}")
        
        self.env['res.partner.profile.history'].create({
            'partner_id': partner.id,
            'old_profile_id': old_profile.id,
            'new_profile_id': new_profile.id,
            'old_score_total': old_score,
            'new_score_total': partner.score_total,
            'score_hectares': partner.score_hectares,
            'score_categories': partner.score_categories,
            'change_trigger': change_trigger,
            'change_reason': ('\n'.join(reason_parts) 
                            if reason_parts else 'Automatic scoring change')
        })

    @api.constrains('category_id')
    def _check_category_groups_unique(self):
        """Ensure only one category per exclusive group."""
        exclusive_groups = [
            'Technology Level', 'Commercial Profile', 
            'Production size', 'Growth perspective'
        ]
        
        for partner in self:
            if not partner.category_id:
                continue

            category_names = partner.category_id.mapped('name')
            
            for group_prefix in exclusive_groups:
                group_categories = [
                    name for name in category_names 
                    if name.startswith(group_prefix)
                ]
                
                if len(group_categories) > 1:
                    raise ValidationError(
                        f"Only one category from '{group_prefix}' group is allowed. "
                        f"Currently assigned: {', '.join(group_categories)}"
                    )

    def write(self, vals):
        """Override write to track profile changes."""
        tracked_fields = ['hectares', 'category_id', 'profile_id']
        has_tracked_changes = any(field in vals for field in tracked_fields)
        
        old_values = {}
        if has_tracked_changes:
            for partner in self:
                if partner.id:
                    old_values[partner.id] = {
                        'hectares': partner.hectares,
                        'category_id': partner.category_id.mapped('name'),
                        'profile_id': partner.profile_id,
                        'score_total': partner.score_total,
                    }
        
        result = super().write(vals)
        
        if has_tracked_changes and old_values:
            for partner in self:
                if partner.id in old_values:
                    self._check_and_create_history_record(partner, old_values[partner.id], vals)
        
        return result
    
    def _check_and_create_history_record(self, partner, old_vals, new_vals):
        """Check for significant changes and create history record."""
        reason_parts = []
        change_trigger = 'manual'
        
        if 'hectares' in new_vals and old_vals['hectares'] != partner.hectares:
            reason_parts.append(f"Hectares: {old_vals['hectares']} → {partner.hectares}")
            change_trigger = 'hectares'
        
        if 'category_id' in new_vals:
            old_cats = set(old_vals['category_id'])
            new_cats = set(partner.category_id.mapped('name'))
            
            if old_cats != new_cats:
                added = new_cats - old_cats
                removed = old_cats - new_cats
                
                if added:
                    reason_parts.append(f"Added: {', '.join(added)}")
                    change_trigger = 'category'
                if removed:
                    reason_parts.append(f"Removed: {', '.join(removed)}")
                    change_trigger = 'category'
        
        profile_changed = 'profile_id' in new_vals and old_vals['profile_id'] != partner.profile_id
        
        if reason_parts or profile_changed:
            if not reason_parts and profile_changed:
                reason_parts.append("Manual profile assignment")
            
            self.env['res.partner.profile.history'].create({
                'partner_id': partner.id,
                'old_profile_id': old_vals['profile_id'].id if old_vals['profile_id'] else False,
                'new_profile_id': partner.profile_id.id if partner.profile_id else False,
                'old_score_total': old_vals['score_total'],
                'new_score_total': partner.score_total,
                'score_hectares': partner.score_hectares,
                'score_categories': partner.score_categories,
                'change_trigger': change_trigger,
                'change_reason': '\n'.join(reason_parts) if reason_parts else 'Profile update'
            })
    
    @api.depends('hectares', 'category_id', 'category_id.score_value', 'category_id.scoring_active')
    def _compute_client_score(self):
        """Compute client scores using dynamic scoring system."""
        for partner in self:
            partner.score_hectares = self._get_hectares_score(partner.hectares)
            partner.score_categories = sum(
                cat.score_value for cat in partner.category_id.filtered('scoring_active')
            )
            partner.score_total = partner.score_hectares + partner.score_categories
    
    def _get_hectares_score(self, hectares):
        """Get hectares score using dynamic ranges."""
        if not hectares:
            return 0.0
            
        hectares_range = self.env['res.partner.hectares.range'].search([
            ('active', '=', True),
            ('min_hectares', '<=', hectares),
            '|',
            ('max_hectares', '>=', hectares),
            ('max_hectares', '=', False)
        ], order='min_hectares desc', limit=1)
        
        return hectares_range.score_value if hectares_range else 0.0
    
    @api.depends('profile_history_ids')
    def _compute_profile_stats(self):
        """Compute profile statistics."""
        for partner in self:
            history = partner.profile_history_ids
            partner.profile_change_count = len(history)
            partner.last_profile_change = history[0].change_date.date() if history else False

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
            raise UserError(_("Please select customers (companies with customer flag enabled)."))
        
        return {
            'name': _('Generate Sale Targets'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.target.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_ids': [(6, 0, partners.ids)],
                'default_date_from': fields.Date.today(),
            }
        }



class ResPartnerHectaresRange(models.Model):
    _name = 'res.partner.hectares.range'
    _description = 'Partner Hectares Range'
    _order = 'min_hectares'
    _rec_name = 'display_name'

    name = fields.Char(string='Classification Name')
    display_name = fields.Char(compute='_compute_display_name', store=True)
    min_hectares = fields.Float(string='Minimum Hectares', required=True)
    max_hectares = fields.Float(string='Maximum Hectares')
    score_value = fields.Float(string='Score Points', required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', 
        default=lambda self: self.env.company
    )

    @api.depends('name', 'min_hectares', 'max_hectares', 'score_value')
    def _compute_display_name(self):
        for record in self:
            range_text = (f"{record.min_hectares} - {record.max_hectares}" 
                         if record.max_hectares 
                         else f"{record.min_hectares}+")
            
            if record.name:
                record.display_name = (f"{record.name} "
                                     f"({range_text} hectares, "
                                     f"{record.score_value} pts)")
            else:
                record.display_name = (f"{range_text} hectares "
                                     f"(Score: {record.score_value})")

    @api.constrains('min_hectares', 'max_hectares')
    def _check_hectares_range(self):
        for record in self:
            if record.min_hectares < 0:
                raise ValidationError("Minimum hectares cannot be negative.")
            if (record.max_hectares and 
                record.max_hectares < record.min_hectares):
                raise ValidationError(
                    "Maximum hectares must be greater than minimum."
                )

    @api.constrains('min_hectares', 'max_hectares', 'active', 'company_id')
    def _check_overlapping_ranges(self):
        for record in self:
            if not record.active:
                continue
                
            existing = self.search([
                ('id', '!=', record.id),
                ('active', '=', True),
                ('company_id', '=', record.company_id.id),
            ])
            
            for other in existing:
                if self._ranges_overlap(record, other):
                    raise ValidationError(
                        f"Range {record.min_hectares}-{record.max_hectares or '∞'} "
                        f"overlaps with {other.min_hectares}-{other.max_hectares or '∞'}"
                    )
    
    def _ranges_overlap(self, range1, range2):
        min1, max1 = range1.min_hectares, range1.max_hectares or float('inf')
        min2, max2 = range2.min_hectares, range2.max_hectares or float('inf')
        return min1 <= max2 and max1 >= min2


class ResPartnerProfileHistory(models.Model):
    _name = 'res.partner.profile.history'
    _description = 'Partner Profile History'
    _order = 'change_date desc, id desc'
    _rec_name = 'display_name'
    
    display_name = fields.Char(compute='_compute_display_name', store=True)
    partner_id = fields.Many2one(
        'res.partner', 
        required=True, 
        ondelete='cascade'
    )
    change_date = fields.Datetime(
        default=fields.Datetime.now, 
        required=True
    )
    old_profile_id = fields.Many2one('res.partner.profile')
    new_profile_id = fields.Many2one('res.partner.profile', required=True)
    old_score_total = fields.Float()
    new_score_total = fields.Float()
    score_hectares = fields.Float()
    score_categories = fields.Float()
    change_trigger = fields.Selection([
        ('manual', 'Manual Assignment'),
        ('hectares', 'Hectares Change'),
        ('category', 'Category Change'),
        ('scoring', 'Scoring Update')
    ], required=True)
    change_reason = fields.Text()
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user)
    company_id = fields.Many2one(
        'res.company', 
        related='partner_id.company_id', 
        store=True
    )
    
    @api.depends('partner_id', 'old_profile_id', 'new_profile_id', 'change_date')
    def _compute_display_name(self):
        for record in self:
            if record.partner_id and record.new_profile_id:
                old_name = (record.old_profile_id.name 
                           if record.old_profile_id else 'None')
                new_name = record.new_profile_id.name
                date_str = (record.change_date.strftime('%Y-%m-%d %H:%M') 
                           if record.change_date else '')
                record.display_name = (f"{record.partner_id.name}: "
                                     f"{old_name} → {new_name} ({date_str})")
            else:
                record.display_name = "Profile Change"


class SaleTargetWizard(models.TransientModel):
    """Sale Target Generation Wizard for mass target creation."""
    
    _name = "sale.target.wizard"
    _description = "Sale Target Generation Wizard"
    
    partner_ids = fields.Many2many(
        'res.partner',
        string="Clients",
        required=True,
        domain=[('is_company', '=', True), ('customer', '=', True)],
    )
    template_id = fields.Many2one(
        'sale.order.template',
        string="Quotation Template", 
        required=True,
    )
    date_from = fields.Date(
        string="Start Date",
        required=True,
        default=fields.Date.today,
    )
    date_to = fields.Date(
        string="End Date", 
        required=True,
    )
    target_count = fields.Integer(
        string="Targets to Create",
        compute="_compute_summary",
        readonly=True
    )
    line_count = fields.Integer(
        string="Target Lines to Create", 
        compute="_compute_summary",
        readonly=True
    )
    validation_errors = fields.Text(
        string="Validation Issues",
        compute="_compute_validation_errors",
        readonly=True
    )
    
    @api.depends('partner_ids', 'template_id')
    def _compute_summary(self):
        for wizard in self:
            wizard.target_count = len(wizard.partner_ids)
            template_lines = wizard.template_id.sale_order_template_line_ids
            wizard.line_count = len(wizard.partner_ids) * len(template_lines)
    
    @api.depends('partner_ids', 'template_id', 'date_from', 'date_to')
    def _compute_validation_errors(self):
        for wizard in self:
            errors = []
            
            if (wizard.date_from and wizard.date_to and 
                wizard.date_from >= wizard.date_to):
                errors.append("End date must be after start date")
            
            no_hectares = wizard.partner_ids.filtered(lambda p: not p.hectares)
            if no_hectares:
                names = ', '.join(no_hectares.mapped('name'))
                errors.append(f"Partners without hectares: {names}")
            
            no_profile = wizard.partner_ids.filtered(lambda p: not p.profile_id)
            if no_profile:
                names = ', '.join(no_profile.mapped('name'))
                errors.append(f"Partners without profile: {names}")
            
            if (wizard.template_id and 
                not wizard.template_id.sale_order_template_line_ids):
                errors.append("Selected template has no product lines")
            
            if wizard.partner_ids and wizard.date_from and wizard.date_to:
                overlapping = self._check_overlapping_targets(wizard)
                if overlapping:
                    names = ', '.join(overlapping)
                    errors.append(f"Overlapping targets found for: {names}")
            
            wizard.validation_errors = '\n'.join(errors) if errors else False
    
    def _check_overlapping_targets(self, wizard):
        overlapping_partners = []
        
        for partner in wizard.partner_ids:
            existing = self.env['sale.target'].search([
                ('partner_id', '=', partner.id),
                ('date_from', '<=', wizard.date_to),
                ('date_to', '>=', wizard.date_from)
            ])
            
            if existing:
                overlapping_partners.append(partner.name)
        
        return overlapping_partners
    
    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wizard in self:
            if (wizard.date_from and wizard.date_to and 
                wizard.date_from >= wizard.date_to):
                raise ValidationError("End date must be after start date.")
    
    def action_generate_targets(self):
        self.ensure_one()
        
        if self.validation_errors:
            raise UserError(
                _("Please select customers (companies with customer flag enabled).")
            )

            raise UserError(f"Please resolve issues:\n{self.validation_errors}")
        
        created_targets = self.env['sale.target']
        
        for partner in self.partner_ids:
            target = self.env['sale.target'].create({
                'partner_id': partner.id,
                'date_from': self.date_from,
                'date_to': self.date_to,
                'template_id': self.template_id.id,
                'user_id': partner.user_id.id if partner.user_id else False,
            })
            
            self._create_target_lines(target, partner)
            created_targets |= target
        
        return self._show_success_result(created_targets)
    
    def _create_target_lines(self, target, partner):
        for template_line in self.template_id.sale_order_template_line_ids:
            if not template_line.product_id or template_line.display_type:
                continue
                
            price = self._calculate_target_price(template_line, partner)
            
            self.env['sale.target.line'].create({
                'target_id': target.id,
                'product_id': template_line.product_id.id,
                'quantity': template_line.product_uom_qty or 1.0,
                'price_unit': price,
            })
    
    def _calculate_target_price(self, template_line, partner):
        if not template_line.product_id:
            return 0.0
        
        pricelist = partner.property_product_pricelist
        if pricelist:
            try:
                return pricelist.get_product_price(
                    template_line.product_id, 1.0, partner,
                    date=fields.Date.today()
                )
            except:
                pass
        
        return template_line.product_id.list_price
    
    def _show_success_result(self, created_targets):
        """Show success notification and open created targets."""
        target_count = len(created_targets)
        line_count = sum(len(target.line_ids) for target in created_targets)
        
        message = _(
            "Successfully created %(target_count)d targets with %(line_count)d lines."
        ) % {
            'target_count': target_count,
            'line_count': line_count
        }
        
        action = self.env.ref('marin.action_sale_target').read()[0]
        action.update({
            'domain': [('id', 'in', created_targets.ids)],
            'context': {}
        })
        
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
