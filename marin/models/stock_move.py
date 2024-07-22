from odoo import api, fields, models


class StockMoveInherit(models.Model):
    _inherit = "stock.move"

    picking_id = fields.Many2one(ondelete="cascade")
    purchase_line_id = fields.Many2one(readonly=False)
    allowed_purchase_line_ids = fields.Many2many(
        comodel_name="purchase.order.line",
        string="Allowed purchase lines to be related",
        compute="_compute_allowed_purchase_line_ids",
    )
    allowed_sale_line_ids = fields.Many2many(
        comodel_name="sale.order.line",
        string="Allowed sale lines to be related",
        compute="_compute_allowed_sale_line_ids",
    )

    def _set_quantity_done_prepare_vals(self, qty):
        res = super()._set_quantity_done_prepare_vals(qty)
        if res and self._context.get("mrp_production") and self.product_id.tracking == "lot":
            for ml in res:
                if ml[0] != 0:
                    continue
                if ml[2].get("lot_id"):
                    continue
                lot = self.move_line_ids.mapped("lot_id")[:1]
                if lot:
                    ml[2]["lot_id"] = lot.id
        return res

    @api.depends("picking_id.group_id", "product_id")
    def _compute_allowed_purchase_line_ids(self):
        purchase_obj = self.env["purchase.order"]
        for rec in self:
            group = rec.picking_id.group_id
            orders = purchase_obj.search([("group_id", "=", group.id)])
            lines = orders.order_line.filtered(lambda line: line.product_id == rec.product_id)
            rec.allowed_purchase_line_ids = lines

    @api.depends("picking_id.sale_id", "product_id")
    def _compute_allowed_sale_line_ids(self):
        for rec in self:
            lines = rec.picking_id.sale_id.order_line.filtered(lambda line: line.product_id == rec.product_id)
            rec.allowed_sale_line_ids = lines

    def _action_confirm(self, merge=True, merge_into=False):
        for move in self:
            if not move.route_ids and move.picking_type_id.route_ids:
                move.route_ids = move.picking_type_id.route_ids
        return super()._action_confirm(merge, merge_into)

    def _get_available_move_lines_in(self):
        res = super()._get_available_move_lines_in()
        if not (self.location_id.usage == "transit" and not self.location_id.company_id):
            return res
        grouped_move_lines_in = {}
        for (location_id, lot_id, package_id, owner_id), quantity in res.items():
            if lot_id and lot_id.company_id != self.company_id:
                lot_id = self._get_company_lot(lot_id)
            grouped_move_lines_in[(location_id, lot_id, package_id, owner_id)] = quantity
        return grouped_move_lines_in

    def _get_company_lot(self, lot):
        existing_lot = self.env["stock.lot"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("name", "=", lot.name),
                ("product_id", "=", lot.product_id.id),
            ],
            limit=1,
        )
        if existing_lot:
            return existing_lot
        new_lot = lot.copy({"company_id": self.company_id.id, "name": lot.name})
        return new_lot

    def _should_bypass_reservation(self, forced_location=False):
        res = super()._should_bypass_reservation(forced_location)
        location = forced_location or self.location_id
        return res or (location.usage == "transit" and not location.company_id)
