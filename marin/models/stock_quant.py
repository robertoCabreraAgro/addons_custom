from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class StockQuant(models.Model):
    """Inherit StockQuant"""

    _inherit = "stock.quant"

    # Extend core fields
    product_categ_id = fields.Many2one(store=True, readonly=True)
    warehouse_id = fields.Many2one(store=True, readonly=True)

    # New fields
    removal_priority = fields.Integer(
        related="location_id.removal_priority", store=True
    )

    def _apply_inventory_group_validate(self):
        if not self.env.user.has_group("marin.group_stock_inventory_adjustment"):
            raise UserError(
                _("Only a inventory manager can validate an inventory adjustment.")
            )

    # Extend original method
    def _apply_inventory(self):
        self._apply_inventory_group_validate()
        super()._apply_inventory()

    # Extend original method
    @api.model
    def _get_removal_strategy(self, product_id, location_id):
        if (
            not product_id.categ_id.removal_strategy_id
            and not location_id.removal_strategy_id
        ):
            return "fefo + priority"
        return super()._get_removal_strategy(product_id, location_id)

    # Extend original method
    @api.model
    def _get_removal_strategy_order(self, removal_strategy):
        if removal_strategy == "fifo + priority":
            return "in_date ASC, removal_priority ASC, id"
        if removal_strategy == "lifo + priority":
            return "in_date DESC, removal_priority ASC, id DESC"
        if removal_strategy == "fefo + priority":
            return "removal_date, removal_priority ASC, id"
        return super()._get_removal_strategy_order(removal_strategy)

    def action_stock_quant_lot_update(self):
        if len(self.company_id) > 1 or any(not q.company_id.id for q in self):
            raise UserError(_("You can only change lots used by a single company."))
        if len(self) > 1:
            raise UserError(_("You can only change lot of one quant at a time."))
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "marin.action_stock_quant_lot_update"
        )
        action["context"] = {"active_model": self._name, "active_ids": self.ids}
        return action
