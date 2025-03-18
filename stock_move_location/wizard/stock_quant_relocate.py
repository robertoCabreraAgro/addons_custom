from odoo import _, api, fields, models
from odoo.osv import expression
import logging

_logger = logging.getLogger(__name__)


class StockQuantRelocate(models.TransientModel):
    _inherit = "stock.quant.relocate"
    _description = "Wizard move location"

    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
    )
    picking_type_id = fields.Many2one(
        comodel_name="stock.picking.type",
        compute="_compute_picking_type_id",
        store=True,
        readonly=False,
        domain="[('company_id', '=', company_id), ('code', '=', 'internal')]",
    )
    location_origin_id = fields.Many2one(
        comodel_name="stock.location",
        string="Origin Location",
        required=True,
        domain="[('company_id', 'in', (company_id, False))]",
        help="Select the origin location where the products are being moved from.",
    )
    location_destination_id = fields.Many2one(
        comodel_name="stock.location",
        string="Destination Location",
        required=True,
        domain="[('company_id', 'in', (company_id, False))]",
        help="Select the destination location where the products are being moved to.",
    )
    picking_id = fields.Many2one(
        comodel_name="stock.picking",
        string="Connected Picking",
    )
    edit_locations = fields.Boolean(
        default=False,
        help="Select this option to enable editing of the origin location.",
    )
    location_origin_readonly = fields.Boolean(
        compute="_compute_locations_readonly",
        help="technical field to disable the edition of origin location.",
    )
    location_destination_readonly = fields.Boolean(
        compute="_compute_locations_readonly",
        help="technical field to disable the edition of destination location.",
    )
    apply_putaway_strategy = fields.Boolean()
    exclude_reserved_qty = fields.Boolean(default=True)
    message = fields.Text("Reason for relocation")
    line_ids = fields.One2many(
        "stock.quant.relocate.line",
        "move_location_wizard_id",
        string="Move Location lines",
    )
    skip_picking = fields.Boolean(
        string="Skip Picking",
        default=False,
        help="If it is active, no pickings will be generated, only movements.",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        if self.env.context.get("active_model", False) != "stock.quant":
            return res

        quants = self.env["stock.quant"].browse(self.env.context.get("active_ids", []))

        res["location_origin_id"] = quants[0].location_id.id
        res["line_ids"] = self._prepare_wizard_move_lines(quants)
        return res

    @api.model
    def _prepare_wizard_move_lines(self, quants):
        res = []
        exclude_reserved_qty = self.env.context.get(
            "only_reserved_qty", self.exclude_reserved_qty
        )
        for quant in quants:
            quantity = quant.quantity
            if exclude_reserved_qty:
                quantity = quant._get_available_quantity(
                    quant.product_id,
                    quant.location_id,
                    quant.lot_id,
                    quant.package_id,
                    quant.owner_id,
                )
            if quantity:
                res.append(
                    (
                        0,
                        0,
                        {
                            "product_id": quant.product_id.id,
                            "move_quantity": quantity,
                            "max_quantity": quantity,
                            "reserved_quantity": quant.reserved_quantity,
                            "total_quantity": quant.quantity,
                            "location_origin_id": quant.location_id.id,
                            "lot_id": quant.lot_id.id,
                            "package_id": quant.package_id.id,
                            "owner_id": quant.owner_id.id,
                            "product_uom_id": quant.product_uom_id.id,
                            "custom": False,
                        },
                    )
                )
        return res

    @api.depends("edit_locations")
    def _compute_locations_readonly(self):
        for rec in self:
            rec.location_origin_readonly = not rec.edit_locations
            rec.location_destination_readonly = False

    @api.onchange("edit_locations")
    def _onchange_edit_locations(self):
        for rec in self:
            rec.location_origin_readonly = not rec.edit_locations

    @api.depends_context("company")
    @api.depends("location_origin_id")
    def _compute_picking_type_id(self):
        for rec in self:
            picking_type = self.env["stock.picking.type"]
            base_domain = [
                ("code", "=", "internal"),
                ("warehouse_id.company_id", "=", self.company_id.id),
            ]
            if rec.location_origin_id:
                location_id = rec.location_origin_id
                if (
                    location_id
                    and rec.picking_type_id
                    and rec.picking_type_id.default_location_src_id == location_id
                ):
                    continue
                while location_id and not picking_type:
                    domain = [("default_location_src_id", "=", location_id.id)]
                    domain = expression.AND([base_domain, domain])
                    picking_type = picking_type.search(domain, limit=1)
                    # Move up to the parent location if no picking type found
                    location_id = not picking_type and location_id.location_id or False
            if not picking_type:
                picking_type = picking_type.search(base_domain, limit=1)
            rec.picking_type_id = picking_type.id

    def _get_group_quants(self):
        location_id = self.location_origin_id
        # Using sql as search_group does not support aggregation functions
        # leading to overhead in queries to DB
        query = """
            SELECT product_id, lot_id, package_id, owner_id, SUM(quantity) AS quantity,
                SUM(reserved_quantity) AS reserved_quantity
            FROM stock_quant
            WHERE location_id = %s
            GROUP BY product_id, lot_id, package_id, owner_id
        """
        self.env.cr.execute(query, (location_id.id,))
        return self.env.cr.dictfetchall()

    def _get_stock_move_location_lines_values(self):
        product_obj = self.env["product.product"]
        quant_obj = self.env["stock.quant"]
        lot_obj = self.env["stock.lot"]
        product_data = []
        exclude_reserved_qty = self.env.context.get(
            "only_reserved_qty", self.exclude_reserved_qty
        )
        if self.line_ids:
            for line in self.line_ids:
                product_data.append(
                    {
                        "product_id": line.product_id.id,
                        "move_quantity": line.move_quantity,
                        "max_quantity": line.max_quantity,
                        "reserved_quantity": line.reserved_quantity,
                        "total_quantity": line.total_quantity,
                        "location_origin_id": line.location_origin_id.id,
                        "location_destination_id": line.location_destination_id.id,
                        "lot_id": line.lot_id.id if line.lot_id else False,
                        "package_id": line.package_id.id if line.package_id else False,
                        "owner_id": line.owner_id.id if line.owner_id else False,
                        "product_uom_id": line.product_uom_id.id,
                        "custom": line.custom,
                    }
                )
            return product_data
        exclude_reserved_qty = self.env.context.get(
            "only_reserved_qty", self.exclude_reserved_qty
        )
        for group in self._get_group_quants():
            product = product_obj.browse(group.get("product_id")).exists()
            # Apply the putaway strategy
            location_dest_id = (
                self.apply_putaway_strategy
                and self.location_destination_id._get_putaway_strategy(product).id
                or self.location_destination_id.id
            )
            res_qty = group.get("reserved_quantity") or 0.0
            if not res_qty:
                lot = lot_obj.browse(group.get("lot_id"))
                quants = quant_obj._gather(product, self.location_origin_id, lot_id=lot)
                res_qty = sum(quants.mapped("reserved_quantity"))
            total_qty = group.get("quantity") or 0.0
            max_qty = total_qty if not exclude_reserved_qty else total_qty - res_qty
            product_data.append(
                {
                    "product_id": product.id,
                    "move_quantity": max_qty,
                    "max_quantity": max_qty,
                    "reserved_quantity": res_qty,
                    "total_quantity": total_qty,
                    "location_origin_id": self.location_origin_id.id,
                    "location_destination_id": location_dest_id,
                    "lot_id": group.get("lot_id") or False,
                    "package_id": group.get("package_id") or False,
                    "owner_id": group.get("owner_id") or False,
                    "product_uom_id": product.uom_id.id,
                    "custom": False,
                }
            )
        return product_data

    @api.onchange("location_destination_id")
    def _onchange_location_destination_id(self):
        for line in self.line_ids:
            line.location_destination_id = self.location_destination_id

    def _create_picking(self):
        return self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type_id.id,
                "location_id": self.location_origin_id.id,
                "location_dest_id": self.location_destination_id.id,
            }
        )

    def group_lines(self):
        lines_grouped = {}
        for line in self.line_ids:
            lines_grouped.setdefault(
                line.product_id.id, self.env["stock.quant.relocate.line"].browse()
            )
            lines_grouped[line.product_id.id] |= line
        return lines_grouped

    def _create_moves(self, picking):
        self.ensure_one()
        groups = self.group_lines()
        moves = self.env["stock.move"]
        for lines in groups.values():
            moves |= self._create_move(picking, lines)
        return moves

    def _get_move_values(self, picking, lines):
        # locations are same for the products
        location_from_id = self.location_origin_id.id
        location_to_id = self.location_destination_id.id
        product = lines[0].product_id
        product_uom_id = product.uom_id.id
        qty = sum(x.move_quantity for x in lines)
        lot_name = lines[0].lot_id.name
        lot_id = self.env["stock.lot"].search(
            [("product_id", "=", product.id), ("name", "=", lot_name)], limit=1
        )
        move_values = {
            "name": product.display_name,
            "location_id": location_from_id,
            "location_dest_id": location_to_id,
            "product_id": product.id,
            "product_uom": product_uom_id,
            "product_uom_qty": qty,
            "location_move": True,
            "lot_ids": lot_id,
        }
        if picking:
            move_values["picking_id"] = picking.id
        return move_values

    def _create_move(self, picking, lines):
        self.ensure_one()
        move = self.env["stock.move"].create(self._get_move_values(picking, lines))
        lines.create_move_lines(picking, move)
        if self.env.context.get("planned"):
            for line in lines:
                quants = self.env["stock.quant"]._gather(
                    line.product_id,
                    line.location_origin_id,
                    lot_id=line.lot_id,
                    package_id=line.package_id,
                    owner_id=line.owner_id,
                    strict=False,
                    qty=line.move_quantity,
                )
                move._update_reserved_quantity(
                    line.move_quantity,
                    line.location_origin_id,
                    quant_ids=quants,
                    lot_id=line.lot_id,
                    package_id=line.package_id,
                    owner_id=line.owner_id,
                    strict=False,
                )
            # Force the state to be assigned, instead of _action_assign,
            # to avoid discarding the selected move_location_line.
            move.state = "assigned"
            move.move_line_ids.write({"state": "assigned"})
        return move

    def _unreserve_moves(self, picking):
        """
        Try to unreserve moves that they has reserved quantity before user
        moves products from a location to other one and change move origin
        location to the new location to assign later.
        :return moves unreserved
        """
        moves_to_reassign = self.env["stock.move"]
        lines_to_ckeck_reverve = self.line_ids.filtered(
            lambda line: (
                line.move_quantity
                > (
                    line.max_quantity
                    if self.exclude_reserved_qty
                    else line.max_quantity - line.reserved_quantity
                )
                and not line.location_origin_id.should_bypass_reservation()
            )
        )
        for line in lines_to_ckeck_reverve:
            move_lines = self.env["stock.move.line"].search(
                [
                    ("state", "=", "assigned"),
                    ("product_id", "=", line.product_id.id),
                    ("location_id", "=", line.location_origin_id.id),
                    ("lot_id", "=", line.lot_id.id),
                    ("package_id", "=", line.package_id.id),
                    ("owner_id", "=", line.owner_id.id),
                    ("quantity", ">", 0.0),
                    ("picking_id", "!=", picking.id),
                ]
            )
            moves_to_unreserve = move_lines.mapped("move_id")
            moves_to_unreserve._do_unreserve()
            moves_to_reassign |= moves_to_unreserve
        return moves_to_reassign

    def _get_picking_action(self, picking_id):
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "stock.action_picking_tree_all"
        )
        form_view = self.env.ref("stock.view_picking_form").id
        action.update(
            {"view_mode": "form", "views": [(form_view, "form")], "res_id": picking_id}
        )
        return action

    def action_move_location(self):
        self.ensure_one()
        if self.skip_picking:
            moves = self._create_moves(picking=None)
            for move in moves:
                self.move_quants_2(move, message="Relocated whitout picking")
        else:
            picking = self.picking_id if self.picking_id else self._create_picking()

            self._create_moves(picking)
            if not self.env.context.get("planned"):
                moves_to_reassign = self._unreserve_moves(picking)
                picking.button_validate()
                moves_to_reassign._action_assign()
            self.picking_id = picking
            return self._get_picking_action(picking.id)

    def _clear_lines(self):
        self.line_ids = False

    def clear_lines(self):
        self._clear_lines()
        return {"type": "ir.action.do_nothing"}

    def move_quants_2(self, moves, message=False):
        message = message or _("Quantity Relocated")
        move_vals = []
        for quant in self:
            move_vals.append(
                quant.with_context(inventory_name=message)._get_inventory_move_values_2(
                    moves
                )
            )
        moves = self.env["stock.move"].create(move_vals)
        moves._action_done()

    def _get_inventory_move_values_2(self, moves):
        self.ensure_one()
        return {
            "name": moves.product_id.name,
            "product_id": moves.product_id.id,
            "product_uom": moves.product_uom.id,
            "product_uom_qty": moves.product_uom_qty,
            "company_id": self.company_id.id or self.env.company.id,
            "state": "confirmed",
            "location_id": moves.location_id.id,
            "location_dest_id": moves.location_dest_id.id,
            "restrict_partner_id": False,
            "is_inventory": True,
            "picked": True,
            "move_line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": moves.product_id.id,
                        "product_uom_id": moves.product_uom.id,
                        "quantity": moves.product_uom_qty,
                        "location_id": moves.location_id.id,
                        "location_dest_id": moves.location_dest_id.id,
                        "company_id": self.company_id.id or self.env.company.id,
                        "lot_id": moves.lot_ids.id,
                        "package_id": False,
                        "result_package_id": False,
                        "owner_id": False,
                    },
                )
            ],
        }
