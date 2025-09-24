from odoo import api, fields, models
from odoo.tools.translate import _


class ApprovalProductLine(models.Model):
    """
    Approval Product Line Model.

    This model represents individual product items that are part of an approval request.
    It is used when the approval category requires product specification (e.g., purchase
    requests, expense approvals with specific items).

    Each line contains:
    - Product selection with automatic description and UOM population
    - Quantity and price information
    - Optional partner association for vendor-specific approvals

    The model ensures multi-company consistency through automatic company checks.
    """

    _name = "approval.product.line"
    _description = "Product Line"
    _check_company_auto = True

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    approval_request_id = fields.Many2one(
        comodel_name="approval.request",
        required=True,
        ondelete="cascade",
        index=True,  # Index for joining with approval requests
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
        index=True,  # Index for product analysis and filtering
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
    price_unit = fields.Float(
        string="Price",
        default=1.0,
    )

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    @api.depends("product_id")
    def _compute_description(self):
        """
        Compute product line description from product information.

        Automatically populates the description field with either the product's
        purchase description (if available) or its display name. Users can
        override this computed value if needed.

        :return: None (sets description field)
        """
        for line in self:
            line.description = (
                line.product_id.description_purchase or line.product_id.display_name
            )

    @api.depends("product_id")
    def _compute_product_uom_id(self):
        """
        Compute the unit of measure from the selected product.

        Automatically sets the UOM to match the product's default UOM.
        This ensures consistency with product configuration while allowing
        users to change it if needed (e.g., ordering in different units).

        :return: None (sets product_uom_id field)
        """
        for line in self:
            line.product_uom_id = line.product_id.uom_id

    # ------------------------------------------------------------
    # ONCHANGE METHODS
    # ------------------------------------------------------------

    @api.onchange("approval_request_id")
    def _onchange_approval_request_id(self):
        """
        Auto-populate partner from approval request when line is created.

        When adding a product line to an approval request that has a partner
        specified, this method automatically copies the partner to the product
        line for consistency. This is particularly useful for purchase approvals
        where all items are from the same vendor.

        :return: None (sets partner_id field)
        """
        if self.approval_request_id and not self.partner_id:
            self.partner_id = self.approval_request_id.partner_id
