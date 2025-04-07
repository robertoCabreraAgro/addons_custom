from odoo import api, fields, models
from odoo.tools import float_compare, float_is_zero


class PurchaseOrderLineInherit(models.Model):
    _inherit = "purchase.order.line"

    # In core this a related field. We need to trigger its value on view, so we can
    # have it even when we're in a NewId
    partner_id = fields.Many2one(depends=["product_id"])

    # New fields
    transfer_state = fields.Selection(
        selection=[
            ("no", "Nothing to receive"),
            ("to do", "To receive"),
            ("partially", "Partially received"),
            ("done", "Fully received"),
            ("over done", "Over received"),
        ],
        default="no",
        compute="_compute_transfer_state",
        store=True,
    )
    force_company_id = fields.Many2one(
        comodel_name="res.company",
        string="Forced Company",
        compute="_compute_force_company_id",
        readonly=False,
        help="Technical field to force company or get it from env user if order don't exist.",
    )
    product_updatable = fields.Boolean(
        string="Can Edit Product",
        default=True,
        compute="_compute_product_updatable",
    )

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

    @api.depends("state", "product_id", "qty_invoiced", "qty_transfered")
    def _compute_product_updatable(self):
        for line in self:
            if line.state in ["done", "cancel"] or (
                line.state == "purchase"
                and (line.qty_invoiced > 0 or line.qty_transfered > 0)
            ):
                line.product_updatable = False
            else:
                line.product_updatable = True

    @api.depends("state", "product_uom_qty", "qty_transfered", "qty_to_transfer")
    def _compute_transfer_state(self):
        """Compute the Reception Status of a PO line. Possible status:
        -no: if the PO is not in status "purchase", we consider that there is nothing to
         receive. This is also the default value if the conditions of no other status is met.
        -to do: we refer to the quantity to receive of the line.
        -partially: the quantity received is lesser than the quantity ordered.
        -done: the quantity received is equal to the quantity ordered.
        """
        precision = self.env["decimal.precision"].precision_get("Product Price")
        for line in self.filtered(lambda l: not l.display_type):
            if line.state != "purchase":
                line.transfer_state = "no"
                continue

            if float_is_zero(line.qty_transfered, precision_digits=precision):
                line.transfer_state = "to do"
            elif not float_is_zero(
                line.qty_transfered, precision_digits=precision
            ) and not float_is_zero(line.qty_to_transfer, precision_digits=precision):
                line.invoice_state = "partially"
            elif (
                float_compare(
                    line.qty_transfered,
                    line.product_uom_qty,
                    precision_digits=precision,
                )
                == 0
            ):
                line.transfer_state = "done"
            elif (
                float_compare(
                    line.qty_transfered,
                    line.product_uom_qty,
                    precision_digits=precision,
                )
                > 0
            ):
                line.transfer_state = "over done"
            else:
                line.transfer_state = "no"

    @api.depends("order_id", "order_id.partner_id", "product_id")
    def _compute_display_name(self):
        name_per_id = self._additional_name_per_id()
        for po_line in self.sudo():
            name = "{} - {}".format(
                po_line.order_id.name,
                po_line.name and po_line.name.split("\n")[0] or po_line.product_id.name,
            )
            additional_name = name_per_id.get(po_line.id)
            if additional_name:
                name = f"{name} {additional_name}"
            po_line.display_name = name

    # ------------------------------------------------------------
    # ONCHANGE METHODS
    # ------------------------------------------------------------

    @api.onchange("force_company_id")
    def _onchange_force_company_id(self):
        """Assign company_id because is used in domains as partner,
        product, taxes..."""
        for line in self:
            line.company_id = line.force_company_id

    # ------------------------------------------------------------
    # ACTION METHODS
    # ------------------------------------------------------------

    def action_purchase_order_form(self):
        self.ensure_one()
        action = self.env.ref("purchase.purchase_form_action")
        form = self.env.ref("purchase.purchase_order_form")
        action = action.read()[0]
        action["views"] = [(form.id, "form")]
        action["res_id"] = self.order_id.id
        return action

    # ------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------

    def _get_partner_display(self):
        self.ensure_one()
        commercial_partner = self.order_id.partner_id.commercial_partner_id
        return f"({commercial_partner.ref or commercial_partner.name})"

    def _additional_name_per_id(self):
        return {po_line.id: po_line._get_partner_display() for po_line in self}
