from odoo import api, fields, models
from odoo.tools import float_compare, float_is_zero


class SaleOrderLine(models.Model):
    """Inherit SaleOrderLine"""

    _inherit = "sale.order.line"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    # Extended fields
    # In core this a related field. We need to trigger its value on view, so we can
    # have it even when we're in a NewId
    partner_id = fields.Many2one(
        depends=["product_id"],
    )

    # New fields
    transfer_state = fields.Selection(
        selection=[
            ("no", "Nothing to deliver"),
            ("to do", "To deliver"),
            ("partially", "Partially delivered"),
            ("done", "Fully delivered"),
            ("over done", "Over delivered"),
        ],
        default="no",
        compute="_compute_transfer_state",
        store=True,
    )
    force_company_id = fields.Many2one(
        comodel_name="res.company",
        string="Forced company",
        compute="_compute_force_company_id",
        readonly=False,
        help="Technical field to force company or get it "
        "from env user if order don't exist.",
    )

    # ------------------------------------------------------------
    # CRUD METHODS
    # ------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("route_id", False):
                order = self.env["sale.order"].browse(vals["order_id"])
                if order.route_id:
                    vals["route_id"] = order.route_id.id
        return super().create(vals_list)

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    @api.depends("order_id")
    def _compute_force_company_id(self):
        """Related company is not computed already when we click create new line"""
        for line in self:
            line.force_company_id = (
                line.order_id.company_id
                # Is not necessary use browse here
                or self.env.context.get("force_company")
                or self.env.company
            )

    @api.depends("state", "product_uom_qty", "qty_transfered", "qty_to_transfer")
    def _compute_transfer_state(self):
        """Compute the Delivery Status of a SO line. Possible status:
        -no: if the SO is not in status "sale", we consider that there is nothing to
         deliver. This is also the default value if the conditions of no other status is met.
        -to do: we refer to the quantity to deliver of the line.
        -partially: the quantity delivered is lesser than the quantity ordered.
        -done: the quantity delivered is equal to the quantity ordered."""
        precision = self.env["decimal.precision"].precision_get("Product Unit")
        for line in self.filtered(lambda l: not l.display_type):
            if line.state != "sale":
                line.transfer_state = "no"
                continue

            if not float_is_zero(line.qty_to_transfer, precision_digits=precision):
                if float_is_zero(line.qty_transfered, precision_digits=precision):
                    line.transfer_state = "to do"
                else:
                    line.transfer_state = "partially"
            elif float_is_zero(line.qty_to_transfer, precision_digits=precision):
                if float_is_zero(line.product_uom_qty, precision_digits=precision):
                    line.transfer_state = "done"
                    continue

                compare = float_compare(
                    line.qty_transfered,
                    line.product_uom_qty,
                    precision_digits=precision,
                )
                if compare == 0:
                    line.transfer_state = "done"
                elif compare > 0:
                    line.transfer_state = "over done"
            else:
                line.transfer_state = "no"

    # ------------------------------------------------------------
    # ONCHANGE METHODS
    # ------------------------------------------------------------

    @api.onchange("force_company_id")
    def _onchange_force_company_id(self):
        """Assign company_id because is used in domains as partner,
        product, taxes..."""
        for line in self:
            line.company_id = line.force_company_id

    @api.onchange("product_id")
    def global_stock_route_product_id_change(self):
        if self.order_id.route_id:
            self.route_id = self.order_id.route_id

    # ------------------------------------------------------------
    # ACTION METHODS
    # ------------------------------------------------------------

    def action_sale_order_form(self):
        self.ensure_one()
        action = self.env.ref("sale.action_orders")
        form = self.env.ref("sale.view_order_form")
        action = action.read()[0]
        action["views"] = [(form.id, "form")]
        action["res_id"] = self.order_id.id
        return action

    # ------------------------------------------------------------
    # VALIDATION METHODS
    # ------------------------------------------------------------

    def _cant_be_unlinked(self):
        if self._context.get("avoid_check_unlink"):
            return False
        return super()._cant_be_unlinked()
