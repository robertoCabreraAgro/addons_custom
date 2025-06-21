from odoo import fields, models


class AccountMoveTemplateLineRun(models.TransientModel):
    _name = "account.move.template.line.run"
    _description = "Wizard Lines to generate move from template"
    _inherit = ["analytic.mixin"]
    _order = "sequence, id"

    wizard_id = fields.Many2one(
        comodel_name="account.move.template.run",
        ondelete="cascade",
    )
    template_line_id = fields.Many2one(
        comodel_name="account.move.template.line",
        string="Template Line",
        help="Reference to the original template line"
    )
    name = fields.Char(string="Label")
    sequence = fields.Integer()
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Partner",
    )
    account_id = fields.Many2one(
        comodel_name="account.account",
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product",
    )
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Unit of Measure",
    )
    quantity = fields.Float(
        string="Quantity",
        digits="Product Unit of Measure",
    )
    price_unit = fields.Float(
        string="Unit Price",
        digits="Product Price",
    )
    tax_ids = fields.Many2many(
        comodel_name="account.tax",
        string="Taxes",
    )
    discount = fields.Float(
        string="Discount (%)",
        digits="Discount",
    )
    balance = fields.Float(
        string="Balance",
        digits="Product Price",
    )
    note = fields.Char()
