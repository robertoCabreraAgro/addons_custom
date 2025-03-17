from odoo import api, fields, models
from odoo.tools.translate import _


class ApprovalProductLine(models.Model):
    _name = "approval.product.line"
    _description = "Product Line"
    _check_company_auto = True

    approval_request_id = fields.Many2one(
        comodel_name="approval.request",
        required=True,
    )
    company_id = fields.Many2one(
        related="approval_request_id.company_id",
        string="Company",
        store=True,
        readonly=True,
        index=True,
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Partner",
        check_company=True,
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Products",
        required=True,
        check_company=True,
    )
    product_template_id = fields.Many2one(
        related="product_id.product_tmpl_id",
        comodel_name="product.template",
    )
    description = fields.Char(
        string="Description",
        required=True,
        compute="_compute_description",
        store=True,
        precompute=True,
        readonly=False,
    )
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Unit",
        compute="_compute_product_uom_id",
        store=True,
        precompute=True,
        readonly=False,
    )
    quantity = fields.Float(
        string="Quantity",
        default=1.0,
    )

    @api.depends("product_id")
    def _compute_description(self):
        for line in self:
            line.description = (
                line.product_id.description_purchase or line.product_id.display_name
            )

    @api.depends("product_id")
    def _compute_product_uom_id(self):
        for line in self:
            line.product_uom_id = line.product_id.uom_id
