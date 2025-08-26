from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _


class StockPickingType(models.Model):
    """Inherit StockPickingType"""

    _inherit = "stock.picking.type"

    default_location_src_id = fields.Many2one(
        tracking=True,
    )
    default_location_dest_id = fields.Many2one(
        tracking=True,
    )

    # Add search
    count_picking_ready = fields.Integer(search="_search_count_picking_ready")
    count_picking_waiting = fields.Integer(search="_search_count_picking_waiting")

    # pos_avoid_locations = fields.Many2many("stock.location")
    route_ids = fields.Many2many(
        "stock.route",
        "stock_route_picking_type",
        "picking_type_id",
        "route_id",
        "Default destination route",
        help="Default route to be used.",
    )

    # Security
    user_can_access_ids = fields.Many2many(
        "res.users",
        "stock_picking_type_res_users_can_access_rel",
        "picking_type_id",
        "user_id",
        string="Allowed users",
        help="Users that can visualize pickings of this type of operation.",
    )
    can_todo_user_ids = fields.Many2many(
        "res.users",
        "stock_picking_type_res_users_can_todo_rel",
        "picking_type_id",
        "user_id",
        string="Users can todo",
        help="Users that can mark as todo pickings of this type of operation.",
    )
    can_validate_user_ids = fields.Many2many(
        "res.users",
        "stock_picking_type_res_users_can_validate_rel",
        "picking_type_id",
        "user_id",
        string="Users can validate",
        help="Users that can validate pickings of this type of operation.",
    )

    require_responsible = fields.Boolean(
        string="Require Responsible",
        default=False,
        help="If checked, picking operations of this type will require "
        "a responsible person to be specified before validation.",
    )

    # This is a bug fix
    @api.constrains("active")
    def _check_active(self):
        for picking_type in self:
            pos_config = self.env["pos.config"].search(
                [("picking_type_id", "=", picking_type.id)], limit=1
            )
            if not picking_type.active and pos_config:
                raise ValidationError(
                    _(
                        "You cannot archive '%s' as it is used by a POS configuration '%s'.",
                        picking_type.name,
                        pos_config.name,
                    )
                )

    def _search_count_picking_ready(self, operator, value):
        if operator not in ["=", "!="] or not isinstance(value, bool):
            raise UserError(_("Operation not supported"))

        picking_type_ids = []
        pickings_groupby = self.env["stock.picking"].read_group(
            [("state", "=", "assigned")], ["picking_type_id"], ["picking_type_id"]
        )
        for picking_type in pickings_groupby:
            picking_type_ids.append(picking_type["picking_type_id"][0])
        return [("id", "in", picking_type_ids)]

    def _search_count_picking_waiting(self, operator, value):
        if operator not in ["=", "!="] or not isinstance(value, bool):
            raise UserError(_("Operation not supported"))

        picking_type_ids = []
        pickings_groupby = self.env["stock.picking"].read_group(
            [("state", "in", ("confirmed", "waiting"))],
            ["picking_type_id"],
            ["picking_type_id"],
        )
        for picking_type in pickings_groupby:
            picking_type_ids.append(picking_type["picking_type_id"][0])
        return [("id", "in", picking_type_ids)]
