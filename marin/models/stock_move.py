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


    @api.depends("picking_id.group_id", "product_id")
    def _compute_allowed_purchase_line_ids(self):
        purchase_obj = self.env["purchase.order"]
        for rec in self:
            group = rec.picking_id.group_id
            orders = purchase_obj.search([("group_id", "=", group.id)])
            lines = orders.order_line_ids.filtered(lambda line: line.product_id == rec.product_id)
            rec.allowed_purchase_line_ids = lines

    @api.depends("picking_id.sale_id", "product_id")
    def _compute_allowed_sale_line_ids(self):
        for rec in self:
            lines = rec.picking_id.sale_id.order_line_ids.filtered(lambda line: line.product_id == rec.product_id)
            rec.allowed_sale_line_ids = lines

    def _action_confirm(self, merge=True, merge_into=False):
        for move in self:
            if not move.route_ids and move.picking_type_id.route_ids:
                move.route_ids = move.picking_type_id.route_ids
        return super()._action_confirm(merge, merge_into)
