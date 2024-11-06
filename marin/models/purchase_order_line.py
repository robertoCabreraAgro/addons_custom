from odoo import api, fields, models
from odoo.tools import float_compare, float_is_zero


class PurchaseOrderLineInherit(models.Model):
    _inherit = "purchase.order.line"

    # In core this a related field. We need to trigger its value on view, so we can
    # have it even when we're in a NewId
    partner_id = fields.Many2one(depends=["product_id"])

    # New fields
    invoice_status = fields.Selection(
        [
            ("no", "Nothing to invoice"),
            ("to invoice", "To bill"),
            ("partially", "Partially billed"),
            ("invoiced", "Fully billed"),
            ("over invoiced", "Over billed"),
        ],
        default="no",
        compute="_compute_invoice_status", store=True,
    )
    qty_to_receive = fields.Float(
        "Quantity to receive",
        digits="Product Unit of measure",
        compute="_compute_qty_to_receive", store=True,
    )
    reception_status = fields.Selection(
        [
            ("no", "Nothing to receive"),
            ("to receive", "To receive"),
            ("partially", "Partially received"),
            ("received", "Received"),
            ("over received", "Over received"),
        ],
        default="no",
        compute="_compute_reception_status", store=True,
    )
    force_company_id = fields.Many2one(
        "res.company",
        "Forced Company",
        compute="_compute_force_company_id",
        readonly=False,
        help="Technical field to force company or get it " "from env user if order don't exist.",
    )
    product_updatable = fields.Boolean(
        "Can Edit Product", default=True, compute="_compute_product_updatable"
    )

    @api.depends("state", "product_uom_qty", "qty_invoiced", "qty_to_invoice")
    def _compute_invoice_status(self):
        precision = self.env["decimal.precision"].precision_get("Product Unit of measure")
        for line in self:
            if line.state not in ("purchase", "done"):
                line.invoice_status = "no"
            elif not float_is_zero(line.qty_to_invoice, precision_digits=precision):
                line.invoice_status = "to invoice"
            elif float_compare(line.qty_invoiced, line.product_uom_qty, precision_digits=precision) < 0:
                line.invoice_status = "partially"
            elif not float_compare(line.qty_invoiced, line.product_uom_qty, precision_digits=precision):
                line.invoice_status = "invoiced"
            elif float_compare(line.qty_invoiced, line.product_uom_qty, precision_digits=precision) > 0:
                line.invoice_status = "over invoiced"
            else:
                line.invoice_status = "no"

    @api.depends("qty_received", "qty_received_manual", "qty_received_method")
    def _compute_qty_to_receive(self):
        for line in self:
            if line.qty_received_method == "manual":
                line.qty_to_receive = line.product_uom_qty - line.qty_received_manual
            elif line.qty_received_method == "stock_moves":
                line.qty_to_receive = line.product_uom_qty - line.qty_received
            else:
                line.qty_to_receive = 0.0

    @api.depends("state", "product_uom_qty", "qty_received")
    def _compute_reception_status(self):
        """Compute the Reception Status of a PO line. Possible status:
        - no: if the PO is not in status "purchase" or "done", we consider that there is nothing to
          receive. This is also the default value if the conditions of no other status is met.
        - to receive: we refer to the quantity to receive of the line.
        - partially: the quantity received is lesser than the quantity ordered.
        - received: the quantity received is equal to the quantity ordered.
        """
        precision = self.env["decimal.precision"].precision_get("Product Unit of measure")
        for line in self:
            if line.state not in ("purchase", "done") or float_is_zero(
                line.product_uom_qty, precision_digits=precision
            ):
                line.reception_status = "no"
            elif float_is_zero(line.qty_received, precision_digits=precision):
                line.reception_status = "to receive"
            elif float_compare(line.qty_received, line.product_uom_qty, precision_digits=precision) < 0:
                line.reception_status = "partially"
            elif not float_compare(line.qty_received, line.product_uom_qty, precision_digits=precision):
                line.reception_status = "received"
            elif float_compare(line.qty_received, line.product_uom_qty, precision_digits=precision) > 0:
                line.reception_status = "over received"
            else:
                line.reception_status = "no"

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

    @api.depends("order_id.state", "product_id", "qty_invoiced", "qty_received")
    def _compute_product_updatable(self):
        for line in self:
            if line.state in ["done", "cancel"] or (
                line.state == "purchase" and (line.qty_invoiced > 0 or line.qty_received > 0)
            ):
                line.product_updatable = False
            else:
                line.product_updatable = True

    def _get_partner_display(self):
        self.ensure_one()
        commercial_partner = self.order_id.partner_id.commercial_partner_id
        return f"({commercial_partner.ref or commercial_partner.name})"

    def _additional_name_per_id(self):
        return {po_line.id: po_line._get_partner_display() for po_line in self}

    @api.depends("order_id.partner_id", "order_id", "product_id")
    def _compute_display_name(self):
        name_per_id = self._additional_name_per_id()
        for po_line in self.sudo():
            name = "{} - {}".format(
                po_line.order_id.name,
                po_line.name and po_line.name.split("\n")[0] or po_line.product_id.name
            )
            additional_name = name_per_id.get(po_line.id)
            if additional_name:
                name = f"{name} {additional_name}"
            po_line.display_name = name

    @api.onchange("force_company_id")
    def _onchange_force_company_id(self):
        """Assign company_id because is used in domains as partner,
        product, taxes..."""
        for line in self:
            line.company_id = line.force_company_id

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        """Create order to correct compute of taxes"""
        if not self.partner_id or self.order_id:
            return

        purchase_order = self.env["purchase.order"]
        new_so = purchase_order.new({"partner_id": self.partner_id, "company_id": self.force_company_id})
        for onchange_method in new_so._onchange_methods["partner_id"]:
            onchange_method(new_so)
        order_vals = new_so._convert_to_write(new_so._cache)
        self.order_id = purchase_order.create(order_vals)

    def action_purchase_order_form(self):
        self.ensure_one()
        action = self.env.ref("purchase.purchase_form_action")
        form = self.env.ref("purchase.purchase_order_form")
        action = action.read()[0]
        action["views"] = [(form.id, "form")]
        action["res_id"] = self.order_id.id
        return action
