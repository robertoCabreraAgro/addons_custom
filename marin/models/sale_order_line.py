from odoo import api, fields, models
from odoo.tools import float_compare, float_is_zero


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    # Extended fields
    # In core this a related field. We need to trigger its value on view, so we can
    # have it even when we're in a NewId
    order_partner_id = fields.Many2one(depends=["product_id"])
    margin_percent = fields.Float(digits="Product Price")

    # New fields
    date_order = fields.Datetime(
        related="order_id.date_order",
        store=True,
        readonly=True,
        index=True,
    )
    delivery_status = fields.Selection(
        [
            ("no", "Nothing to deliver"),
            ("to deliver", "To deliver"),
            ("partially", "Partially delivered"),
            ("delivered", "Delivered"),
            ("over delivered", "Over delivered"),
        ],
        default="no",
        compute="_compute_delivery_status",
        store=True,
    )
    force_company_id = fields.Many2one(
        "res.company",
        "Forced company",
        compute="_compute_force_company_id",
        readonly=False,
        help="Technical field to force company or get it "
        "from env user if order don't exist.",
    )

    @api.depends("state", "product_uom_qty", "qty_delivered")
    def _compute_delivery_status(self):
        """Compute the Delivery Status of a SO line. Possible status:
        - no: if the SO is not in status "sale" or "done", we consider that there is nothing to
          deliver. This is also the default value if the conditions of no other status is met.
        - to deliver: we refer to the quantity to deliver of the line.
        - partially: the quantity delivered is lesser than the quantity ordered.
        - delivered: the quantity delivered is equal to the quantity ordered.
        """
        precision = self.env["decimal.precision"].precision_get(
            "Product Unit of measure"
        )
        for line in self:
            if line.state not in ("sale", "done") or float_is_zero(
                line.product_uom_qty, precision_digits=precision
            ):
                line.delivery_status = "no"
            elif float_is_zero(line.qty_delivered, precision_digits=precision):
                line.delivery_status = "to deliver"
            elif (
                float_compare(
                    line.qty_delivered, line.product_uom_qty, precision_digits=precision
                )
                < 0
            ):
                line.delivery_status = "partially"
            elif not float_compare(
                line.qty_delivered, line.product_uom_qty, precision_digits=precision
            ):
                line.delivery_status = "delivered"
            elif (
                float_compare(
                    line.qty_delivered, line.product_uom_qty, precision_digits=precision
                )
                > 0
            ):
                line.delivery_status = "over delivered"
            else:
                line.delivery_status = "no"

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

    @api.onchange("force_company_id")
    def _onchange_force_company_id(self):
        """Assign company_id because is used in domains as partner,
        product, taxes..."""
        for line in self:
            line.company_id = line.force_company_id

    @api.onchange("order_partner_id")
    def _onchange_order_partner_id(self):
        """Create order to correct compute of taxes"""
        if not self.order_partner_id or self.order_id:
            return
        sale_order = self.env["sale.order"]
        new_so = sale_order.new(
            {"partner_id": self.order_partner_id, "company_id": self.force_company_id}
        )
        for onchange_method in new_so._onchange_methods["partner_id"]:
            onchange_method(new_so)
        order_vals = new_so._convert_to_write(new_so._cache)
        self.order_id = sale_order.create(order_vals)

    @api.onchange("product_id")
    def global_stock_route_product_id_change(self):
        if self.order_id.route_id:
            self.route_id = self.order_id.route_id

    def action_sale_order_form(self):
        self.ensure_one()
        action = self.env.ref("sale.action_orders")
        form = self.env.ref("sale.view_order_form")
        action = action.read()[0]
        action["views"] = [(form.id, "form")]
        action["res_id"] = self.order_id.id
        return action

    def _check_line_unlink(self):
        if self._context.get("avoid_check_unlink"):
            return False
        return super()._check_line_unlink()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("route_id", False):
                order = self.env["sale.order"].browse(vals["order_id"])
                if order.route_id:
                    vals["route_id"] = order.route_id.id
        return super().create(vals_list)
