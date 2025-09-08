import logging

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    """Inherit StockPicking"""

    _inherit = "stock.picking"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    # New fields
    suitable_product_ids = fields.Many2many(
        comodel_name="product.product",
        compute="_compute_suitable_product_ids",
    )
    suitable_location_dest_ids = fields.Many2many(
        comodel_name="stock.location",
        compute="_compute_suitable_location_dest_ids",
    )
    suitable_location_ids = fields.Many2many(
        comodel_name="stock.location",
        compute="_compute_suitable_location_ids",
    )
    tracker_id = fields.Many2one(
        comodel_name="stock.picking.tracker",
        tracking=True,
        copy=False,
        help="Route tracker record that manages this transfer as part of a delivery route.",
    )
    vehicle_id = fields.Many2one(
        related="tracker_id.vehicle_id",
        store=True,
        readonly=True,
    )
    odometer_done = fields.Float(
        string="Odometer Done",
        tracking=True,
        help="Odometer which the transfer has been processed.",
    )
    odometer_done_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Odometer Unit",
        related="vehicle_id.odometer_uom_id",
        readonly=True,
        store=True,
        help="Unit of measurement for the odometer, coming from the vehicle.",
    )
    fuel_done = fields.Float(
        string="Fuel Done",
        tracking=True,
        help="Fuel level percentage which the transfer has been processed.",
    )
    waiting_warning = fields.Text(compute="_compute_waiting_warning")
    show_purchase_lines = fields.Boolean(compute="_compute_show_purchase_lines")
    show_sale_lines = fields.Boolean(compute="_compute_show_sale_lines")
    show_mark_as_todo = fields.Boolean(compute="_compute_custom_permissions")
    show_validate = fields.Boolean(compute="_compute_custom_permissions")
    require_responsible = fields.Boolean(
        related="picking_type_id.require_responsible",
        store=False,
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------

    def _compute_custom_permissions(self):
        for picking in self:
            vals = picking._prepare_compute_custom_permissions()
            picking.update(vals)

    @api.depends("state")
    def _compute_waiting_warning(self):
        for picking in self:
            picking.waiting_warning = (
                _(
                    "All products could not be reserved. Click on the 'Check Availability' button to try to "
                    "reserve products."
                )
                if picking.state == "confirmed"
                else ""
            )

    @api.depends("picking_type_id", "state")
    def _compute_suitable_location_dest_ids(self):
        self.suitable_location_dest_ids = self.env["stock.location"].search([("usage", "=", "internal")])
        for picking in self.filtered(
            lambda p: p.state not in ("cancel", "done") and p.picking_type_id.code in ("internal", "incoming")
        ):
            self.suitable_location_dest_ids = self.suitable_location_dest_ids.filtered(
                lambda location: location.warehouse_id == picking.picking_type_id.warehouse_id
            )

    @api.depends("picking_type_id", "state")
    def _compute_suitable_location_ids(self):
        self.suitable_location_ids = self.env["stock.location"].search([("usage", "=", "internal")])
        for picking in self.filtered(
            lambda p: p.state not in ("cancel", "done") and p.picking_type_id.code in ("internal", "outgoing")
        ):
            self.suitable_location_ids = self.suitable_location_ids.filtered(
                lambda location: location.warehouse_id == picking.picking_type_id.warehouse_id
            )

    @api.depends("picking_type_id", "location_id")
    def _compute_suitable_product_ids(self):
        suitable_product_ids = self.env["product.product"].search([("type", "=", "consu")])
        for picking in self.filtered(
            lambda p: p.state not in ("cancel", "done") and p.picking_type_id.code in ("internal", "outgoing")
        ):
            code = picking.picking_type_id.code
            if code == "internal":
                suitable_product_ids = suitable_product_ids.filtered(
                    lambda product: product.stock_quant_ids.filtered(
                        lambda quant: quant.location_id.usage == "internal"
                        and quant.location_id == picking.location_id
                    )
                )

            elif code == "outgoing":
                suitable_product_ids = suitable_product_ids.filtered(
                    lambda product: product.stock_quant_ids.filtered(
                        lambda quant: quant.location_id.usage == "internal"
                        and quant.warehouse_id == picking.picking_type_id.warehouse_id
                    )
                )
        self.suitable_product_ids = suitable_product_ids

    @api.depends("group_id")
    def _compute_show_purchase_lines(self):
        for rec in self:
            order = rec.env["purchase.order"].search([("procurement_group_id", "=", rec.group_id.id)])
            to_from_supplier = rec.location_id.usage == "supplier" or rec.location_dest_id.usage == "supplier"
            rec.show_purchase_lines = bool(order and to_from_supplier)

    @api.depends("sale_id")
    def _compute_show_sale_lines(self):
        for rec in self:
            to_from_customer = rec.location_dest_id.usage == "customer" or rec.location_id.usage == "customer"
            rec.show_sale_lines = bool(rec.sale_id and to_from_customer)

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------

    def action_view_purchase_order(self):
        self.ensure_one()
        # Remove default_picking_id to avoid defaults get
        # https://github.com/odoo/odoo/blob/master/addons/stock/models/stock_move.py#L624
        ctx = self.env.context.copy()
        ctx.pop("default_picking_id", False)
        return self.with_context(ctx).purchase_id.get_formview_action()

    def action_view_sale_order(self):
        self.ensure_one()
        # Remove default_picking_id to avoid defaults get
        # https://github.com/odoo/odoo/blob/master/addons/stock/models/stock_move.py#L624
        ctx = self.env.context.copy()
        ctx.pop("default_picking_id", False)
        return self.with_context(ctx).sale_id.get_formview_action()

    def action_view_moves(self):
        action = self.env["ir.actions.act_window"]._for_xml_id("stock.stock_move_action")
        action["domain"] = [("id", "in", self.move_ids.ids)]
        action["context"] = {
            "search_default_future": 1,
            "search_default_by_product": 1,
            "search_default_groupby_picking_type_id": 1,
            "pivot_measures": ["product_uom_qty", "__count__"],
        }
        return action

    def _action_done(self):
        res = super()._action_done()
        for picking in self.filtered(lambda p: p.picking_type_id.code == "outgoing" and p.vehicle_id):
            picking._update_gps_tracking_information()
        return res

    def button_validate(self):
        """Override to add responsible validation."""
        for picking in self:
            if picking.require_responsible and not picking.user_id:
                raise UserError(
                    self.env._(
                        "The responsible person is required for %s operations. "
                        "Please specify who is responsible for this %s."
                    )
                    % (
                        picking.picking_type_id.name,
                        ("reception" if picking.picking_type_id.code == "incoming" else "delivery"),
                    )
                )
        return super().button_validate()

    # backport V17
    def action_draft(self):
        picking_to_reset = self.filtered(lambda p: p.state == "cancel")
        picking_to_reset.do_unreserve()
        picking_to_reset.move_ids.state = "draft"
        picking_to_reset.move_ids.quantity = 0
        picking_to_reset.move_ids.move_line_ids.unlink()

    @api.model
    def _print_deliveryslip(self):
        self._validate_deliveryslip()
        return self.env.ref("stock.action_report_delivery").report_action(self)

    @api.model
    def _print_picking_operation(self):
        self._validate_picking_operation()
        return self.env.ref("stock.action_report_picking").report_action(self)

    def _update_gps_tracking_information(self, date=False):
        gps_tracking_device = self.env["gps.tracking.device"].sudo()
        for picking in self:
            vehicle = picking.vehicle_id
            gps_device = picking.vehicle_id.gps_device_id
            if not gps_device and vehicle:
                gps_device = gps_tracking_device.search([("asset_id", "=", vehicle.id)], limit=1)
            picking.write(
                {
                    "odometer_done": gps_device.get_odometer(date) if gps_device else 0.0,
                    "fuel_done": gps_device.get_fuel_level_percentage(date) if gps_device else 0.0,
                }
            )

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _prepare_compute_custom_permissions(self):
        self.ensure_one()
        show_mark_as_todo = self.state == "draft" and self.env.user in self.picking_type_id.can_todo_user_ids
        show_validate = (
            self.state in ("confirmed", "assigned") and self.env.user in self.picking_type_id.can_validate_user_ids
        )
        return {
            "show_mark_as_todo": show_mark_as_todo,
            "show_validate": show_validate,
        }

    # ------------------------------------------------------------
    # VALIDATIONS
    # ------------------------------------------------------------

    def _validate_deliveryslip(self):
        invalid_pickings = self.filtered(lambda pick: pick.state != "done")
        if invalid_pickings:
            picking_names = "\n".join(picking.name for picking in invalid_pickings)
            raise UserError(
                _(
                    "Following pickings are not valid to print their delivery slip: \n%s",
                    picking_names,
                )
            )
        return True

    def _validate_picking_operation(self):
        invalid_pickings = self.filtered(
            lambda pick: pick.state != "assigned"
            and not (
                pick.state == "confirmed"
                and pick.move_ids.filtered(lambda sm: sm.state in ["partially_available", "assigned"])
            )
        )
        if invalid_pickings:
            picking_names = "\n".join(picking.name for picking in invalid_pickings)
            raise UserError(
                _(
                    "Following pickings are not valid to print their picking operation: \n%s",
                    picking_names,
                )
            )
        return True
