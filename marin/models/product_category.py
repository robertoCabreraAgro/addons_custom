from odoo import api, fields, models


class ProductCategoryInherit(models.Model):
    _inherit = "product.category"


    property_account_income_refund_id = fields.Many2one(
        "account.account",
        "Income Refund Account",
        company_dependent=True,
        domain=[("deprecated", "=", False)],
        help="Used as default value on the customer credit notes lines. "
             "Leave empty to use the income account.",
    )
    property_account_expense_refund_id = fields.Many2one(
        "account.account",
        "Expense Refund Account",
        company_dependent=True,
        domain=[("deprecated", "=", False)],
        help="Used as default value on the vendor refunds lines. "
             "Leave empty to use the expense account.",
    )
    expiration_time = fields.Integer(
        string="Expiration Date",
        help="Number of days after the receipt of the products (from the vendor "
             "or in stock after production) after which the goods may become dangerous "
             "and must not be consumed. It will be computed on the lot/serial number.",
    )
    use_time = fields.Integer(
        string="Best Before Date",
        help="Number of days before the Expiration Date after which the goods starts to "
             "deteriorate. It will be computed on the lot/serial number.",
    )
    removal_time = fields.Integer(
        string="Removal Date",
        help="Number of days before the Expiration Date after which the goods "
             "should be removed from the stock. It will be computed on the lot/serial number.",
    )
    alert_time = fields.Integer(
        string="Alert Date",
        help="Number of days before the Expiration Date after which an alert should be "
             "raised on the lot/serial number. It will be computed on the lot/serial number.",
    )
    root_categ_id = fields.Many2one(
        "product.category", string="Root Category",
        compute="_compute_root_category", store=True,
        recursive=True, index=True)


    @api.depends("parent_id.root_categ_id")
    def _compute_root_category(self):
        for categ in self:
            if not categ.parent_id:
                categ.root_categ_id = categ
            else:
                categ.root_categ_id = categ.parent_id.root_categ_id
