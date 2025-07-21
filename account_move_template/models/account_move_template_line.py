import random
from odoo import api, fields, models
from odoo.exceptions import ValidationError, UserError
from odoo.tools.translate import _


class AccountMoveTemplateLine(models.Model):
    _name = "account.move.template.line"
    _description = "Journal Item Template"
    _inherit = ["analytic.mixin"]
    _order = "sequence, id"
    _check_company_auto = True

    template_id = fields.Many2one(
        comodel_name="account.move.template",
        string="Move Template",
        required=True,
        ondelete="cascade",
        index=True,
    )
    display_type = fields.Selection(
        selection=[
            ("product", "Product"),
            ("payment_term", "Payment Term"),
            ("line_section", "Section"),
            ("line_note", "Note"),
        ],
        required=True,
        default="product",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Partner",
        domain=["|", ("parent_id", "=", False), ("is_company", "=", True)],
    )
    account_id = fields.Many2one(
        comodel_name="account.account",
        string="Account",
        check_company=True,
        domain=[("deprecated", "=", False), ("account_type", "!=", "off_balance")],
        readonly=False,
        store=False,
    )
    account_code = fields.Char(
        string="Accounts Prefix",
        required=True,
        help="When creating a new journal item an account having this prefix"
        "will be looked for",
    )
    name = fields.Char(string="Label")
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one(
        comodel_name="product.product",
        check_company=True,
    )
    product_category_id = fields.Many2one(
        comodel_name="product.category",
        string="Product Category",
        help="If set, a random product will be selected from this category (and subcategories) when generating the move.",
    )
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Unit of Measure",
        compute="_compute_product_uom_id",
        store=True,
        readonly=False,
    )
    quantity = fields.Float(
        string="Quantity",
        digits="Product Unit of Measure",
        default=1.0,
    )
    price_unit = fields.Float(
        string="Unit Price",
        digits="Product Price",
    )
    tax_ids = fields.Many2many(
        comodel_name="account.tax",
        string="Taxes",
        check_company=True,
    )
    discount = fields.Float(
        string="Discount (%)",
        digits="Discount",
    )
    balance = fields.Float(
        string="Balance",
        digits="Product Price",
    )

    _unique_template_sequence = models.UniqueIndex(
        "(template_id, sequence)",
        "The sequence of the line must be unique per template!",
    )

    @api.constrains("product_id", "product_category_id")
    def _check_product_or_category(self):
        """Ensure only one of product_id or product_category_id is set."""
        for line in self:
            if line.product_id and line.product_category_id:
                raise ValidationError(
                    _(
                        "You can set either a specific product or a product category, not both."
                    )
                )

    @api.depends("product_id")
    def _compute_product_uom_id(self):
        """Compute product UoM based on selected product."""
        for line in self:
            if line.product_id:
                line.product_uom_id = line.product_id.uom_id
            else:
                line.product_uom_id = False

    @api.onchange("account_id")
    def _onchange_account_id(self):
        """Update account code when account changes."""
        if not self.account_id:
            return

        self.account_code = self.account_id.code_store
        self.account_id = False

    @api.onchange("product_category_id")
    def _onchange_product_category_id(self):
        """Clear product_id when product_category_id is set."""
        if self.product_category_id:
            self.product_id = False

    @api.onchange("product_id")
    def _onchange_product_id(self):
        """Clear product_category_id when product_id is set."""
        if self.product_id:
            self.product_category_id = False

    def get_random_product_for_category(self, category):
        """
        Get a random product from the specified category and its subcategories.
        The product must have exclusively supplier_taxes_id = 1029 (VAT 0%).

        Args:
            category: product.category record

        Returns:
            product.product record

        Raises:
            UserError: If no suitable product is found
        """
        # Get all category IDs including subcategories
        category_ids = category.search([("id", "child_of", category.id)]).ids

        # Search for products in these categories with the required tax
        products_with_tax = self.env["product.product"].search(
            [
                ("categ_id", "in", category_ids),
                ("supplier_taxes_id", "in", [1029]),
                ("active", "=", True),
            ]
        )

        # Filter products that have ONLY the VAT 0% tax (ID 1029)
        filtered_products = products_with_tax.filtered(
            lambda p: set(p.supplier_taxes_id.ids) == {1029}
        )

        if not filtered_products:
            raise UserError(
                _(
                    "No product found in category '%s' with exclusively VAT 0%% tax (ID: 1029)."
                )
                % category.display_name
            )

        # Return a random product from the filtered list
        return random.choice(filtered_products)
