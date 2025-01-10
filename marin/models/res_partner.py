from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.tools.misc import formatLang


class ResPartner(models.Model):
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
    credit_limit = fields.Float(tracking=True, help="Receivable limit specific to this partner.")

    # New fields
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
    credit_on_hold = fields.Boolean("Credit on hold", company_dependent=True)
    credit_limit_available = fields.Monetary(
        "Available Receivable Limit",
        compute="_compute_available_debt_limits",
        readonly=True,
        help="Available receivable limit",
    )
    debit_on_hold = fields.Boolean("Debit on hold", company_dependent=True)
    collateral_tolerance = fields.Selection(
        [
            ("0", "No tolerance"),
            ("1", "Medium"),
            ("2", "No collateral required"),
        ],
        string="Collateral tolerance",
        default="0",
        help="""When sales are done with credit this indicates the tolerance
        regarding having collaterales to cover the debt.\n
        -No tolerance: cover the debt in full with collaterals
        -Medium: cover the debt with a payment note
        -No collateral required: The customer have high moral and economical
        solvency so no collateral needed
        """
    )
    # Misc
    customer = fields.Boolean()
    supplier = fields.Boolean()
    competitor = fields.Boolean()
    gender = fields.Selection([("male", "Male"), ("female", "Female"), ("other", "Other")])
    birthdate = fields.Date()
    age = fields.Integer(compute="_compute_age", readonly=True)
    age_range_id = fields.Many2one(
        "res.partner.age.range",
        "Age Range",
        compute="_compute_age_range_id", store=True,
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
        "Social style color"
    )
    team_id = fields.Many2one(
        'crm.team',
        'Sales Team',
        compute='_compute_team_id', store=True, precompute=True,  # avoid queries post-create
        readonly=False,
        ondelete='set null',
    )

    def _prepare_compute_group(self):
        return {
            "user_account_user": self.env.user.has_group("account.group_account_user"),
            "user_debt_manager": self.env.user.has_group("marin.group_account_debt_manager"),
            "user_hr_user": self.env.user.has_group("marin.group_hr_user"),
            "user_hr_manager": self.env.user.has_group("marin.group_hr_manager"),
            "user_purchase_manager": self.env.user.has_group("purchase.group_purchase_manager"),
            "user_sale_manager": self.env.user.has_group("sales_team.group_sale_manager"),
            "user_stock_user": self.env.user.has_group("marin.group_stock_user"),
            "user_stock_manager": self.env.user.has_group("marin.group_stock_manager"),
        }

    def _compute_group(self):
        for partner in self:
            vals = self._prepare_compute_group()
            partner.update(vals)

    @api.depends('parent_id')
    def _compute_team_id(self):
        for partner in self.filtered(
            lambda partner: 
                not partner.team_id
                and partner.company_type == 'person'
                and partner.parent_id.team_id
        ):
            partner.team_id = partner.parent_id.team_id

    @api.depends("birthdate")
    def _compute_age(self):
        for partner in self:
            partner.age = False
            if partner.birthdate:
                partner.age = relativedelta(fields.Date.today(), partner.birthdate).years

    @api.depends("age")
    def _compute_age_range_id(self):
        age_ranges = self.env["res.partner.age.range"].search([])
        for partner in self:
            if partner.age >= 0:
                age_range = age_ranges.filtered(
                    lambda age_range: age_range.age_from <= partner.age <= age_range.age_to
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

    def _compute_available_debt_limits(self):
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
            formatLang(self.env, self.credit_limit_available, currency_obj=currency)
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
