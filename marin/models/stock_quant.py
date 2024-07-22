from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare

from odoo.addons.stock.models.stock_quant import StockQuant


class StockQuantInherit(models.Model):
    _inherit = "stock.quant"

    # Extend core fields
    product_categ_id = fields.Many2one(store=True, readonly=True)
    warehouse_id = fields.Many2one(store=True, readonly=True)
    # New fields
    removal_priority = fields.Integer(related="location_id.removal_priority", store=True)

    def _apply_inventory_group_validate(self):
        if not self.env.user.has_group("marin.group_stock_inventory_adjustment"):
            raise UserError(_("Only a Inventory manager can validate an inventory adjustment."))

    def _apply_inventory2(self):
        move_vals = []
        self._apply_inventory_group_validate()
        for quant in self:
            # Create and validate a move so that the quant matches its `inventory_quantity`.
            if float_compare(quant.inventory_diff_quantity, 0, precision_rounding=quant.product_uom_id.rounding) > 0:
                move_vals.append(
                    quant._get_inventory_move_values(
                        quant.inventory_diff_quantity,
                        quant.product_id.with_company(quant.company_id).property_stock_inventory,
                        quant.location_id,
                    )
                )
            else:
                move_vals.append(
                    quant._get_inventory_move_values(
                        -quant.inventory_diff_quantity,
                        quant.location_id,
                        quant.product_id.with_company(quant.company_id).property_stock_inventory,
                        package_id=quant.package_id,
                    )
                )
        moves = self.env["stock.move"].with_context(inventory_mode=False).create(move_vals)
        moves._action_done()
        self.location_id.write({"last_inventory_date": fields.Date.today()})
        date_by_location = {loc: loc._get_next_inventory_date() for loc in self.mapped("location_id")}
        for quant in self:
            quant.inventory_date = date_by_location[quant.location_id]
        self.write({"inventory_quantity": 0, "user_id": False})
        self.write({"inventory_diff_quantity": 0})

    StockQuant._apply_inventory = _apply_inventory2

    def action_view_inventory_group_validate(self, action):
        if self.env.user.has_group(
            """stock.group_stock_user,!stock.group_stock_manager,
        !marin.group_stock_inventory_adjustment"""
        ):
            action["search_default_my_count"] = True
        return action

    # Extend original method
    @api.model
    def action_view_inventory(self):
        action = super().action_view_inventory()
        return self.action_view_inventory_group_validate(action)

    # Extend original method
    @api.model
    def _get_removal_strategy(self, product_id, location_id):
        if not product_id.categ_id.removal_strategy_id and not location_id.removal_strategy_id:
            return "fefo + priority"
        return super()._get_removal_strategy(product_id, location_id)

    # Extend original method
    @api.model
    def _get_removal_strategy_domain_order(self, domain, removal_strategy, qty):
        if removal_strategy == "fifo + priority":
            return domain, "in_date ASC, removal_priority ASC, id"
        if removal_strategy == "lifo + priority":
            return domain, "in_date DESC, removal_priority ASC, id DESC"
        if removal_strategy == "closest + priority":
            return domain, "removal_priority ASC, location_id ASC, id DESC"
        if removal_strategy == "fefo + priority":
            return domain, "removal_date, removal_priority ASC, id"
        return super()._get_removal_strategy_domain_order(domain, removal_strategy, qty)

    # Extend original method
    def _get_removal_strategy_sort_key(self, removal_strategy):
        reverse = False
        if removal_strategy == "fifo + priority":
            return lambda q: (q.in_date, q.removal_priority, q.id), reverse
        if removal_strategy == "lifo + priority":
            reverse = True
            return lambda q: (-q.in_date, q.removal_priority, -q.id), reverse
        if removal_strategy == "closest + priority":
            return lambda q: (q.location_id.complete_name, q.removal_priority - q.id), reverse
        if removal_strategy == "fefo + priority":
            return lambda q: (q.removal_date, q.in_date, q.removal_priority, q.id), reverse
        return super()._get_removal_strategy_sort_key(removal_strategy)

    def action_stock_quant_lot(self):
        if len(self.company_id) > 1 or any(not q.company_id.id for q in self):
            raise UserError(_("You can only change lots used by a single company."))
        if len(self) > 1:
            raise UserError(_("You can only change lot of one quant at a time."))
        action = self.env["ir.actions.act_window"]._for_xml_id("marin.stock_quant_lot_wizard")
        action["context"] = {"active_model": self._name, "active_ids": self.ids}
        return action
