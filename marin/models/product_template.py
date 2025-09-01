from odoo import api, fields, models


class ProductTemplate(models.Model):
    """Inherit ProductTemplate"""

    _inherit = "product.template"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    sale_ok = fields.Boolean(
        compute="_compute_sale_ok",
        store=True,
        readonly=False,
    )

    user_product_cost_readonly = fields.Boolean(compute="_compute_group")
    user_product_cost_manager = fields.Boolean(compute="_compute_group")
    user_purchase_readonly = fields.Boolean(compute="_compute_group")
    user_purchase_manager = fields.Boolean(compute="_compute_group")
    user_sale_readonly = fields.Boolean(compute="_compute_group")
    user_sale_manager = fields.Boolean(compute="_compute_group")
    user_stock_readonly = fields.Boolean(compute="_compute_group")
    user_stock_manager = fields.Boolean(compute="_compute_group")
    property_account_income_refund_id = fields.Many2one(
        "account.account",
        "Income Refund Account",
        company_dependent=True,
        domain=[("deprecated", "=", False)],
        help="Used as default value on the customer credit notes lines. "
        "Leave empty to use the account from the product category.",
    )
    property_account_expense_refund_id = fields.Many2one(
        "account.account",
        "Expense Refund Account",
        company_dependent=True,
        domain=[("deprecated", "=", False)],
        help="Used as default value on the vendor refunds lines. "
        "Leave empty to use the account from the product category.",
    )
    use_dose = fields.Boolean(
        compute="_compute_use_expiration_date",
        store=True,
        readonly=False,
    )
    x_dose = fields.Float(
        "Dose per Hectare",
        digits="Product Price",
    )
    use_expiration_date = fields.Boolean(
        compute="_compute_use_expiration_date",
        store=True,
        readonly=False,
    )

    def _compute_group(self):
        for product in self:
            vals = self._prepare_compute_group()
            product.update(vals)

    def _compute_sale_ok(self):
        default_sale_ok = self.env.context.get("default_sale_ok", False)
        for product in self:
            if default_sale_ok:
                product.sale_ok = default_sale_ok

    @api.depends("categ_id")
    def _compute_use_dose(self):
        for product in self:
            if product.categ_id and product.categ_id.use_dose:
                product.use_dose = True

    @api.depends("categ_id")
    def _compute_use_expiration_date(self):
        for product in self:
            if product.categ_id and product.categ_id.use_expiration_date:
                product.use_expiration_date = True

    # Extend original method
    def _get_product_accounts(self):
        accounts = super()._get_product_accounts()
        accounts.update(
            {
                "income_refund": self.property_account_income_refund_id
                or self.categ_id.property_account_income_refund_id
                or accounts.get("expense"),
                "expense_refund": self.property_account_expense_refund_id
                or self.categ_id.property_account_expense_refund_id
                or accounts.get("income"),
            }
        )
        return accounts

    def _prepare_compute_group(self):
        return {
            "user_product_cost_readonly": self.env.user.has_group(
                "marin.group_product_cost_readonly"
            ),
            "user_product_cost_manager": self.env.user.has_group(
                "marin.group_product_cost_manager"
            ),
            "user_purchase_readonly": self.env.user.has_group(
                "marin.group_purchase_readonly"
            ),
            "user_purchase_manager": self.env.user.has_group(
                "purchase.group_purchase_manager"
            ),
            "user_sale_readonly": self.env.user.has_group("marin.group_sale_readonly"),
            "user_sale_manager": self.env.user.has_group(
                "sales_team.group_sale_manager"
            ),
            "user_stock_readonly": self.env.user.has_group(
                "marin.group_stock_readonly"
            ),
            "user_stock_manager": self.env.user.has_group("marin.group_stock_manager"),
        }
