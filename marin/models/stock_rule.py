from odoo import models


class StockRule(models.Model):
    _inherit = "stock.rule"

    def _push_prepare_move_copy_values(self, move_to_copy, new_date):
        res = super()._push_prepare_move_copy_values(move_to_copy, new_date)
        location = move_to_copy.location_dest_id
        if location.usage == "transit" and not location.company_id:
            if not res.get("move_orig_ids"):
                res.update({"move_orig_ids": [(4, move_to_copy.id)]})
            if not res.get("group_id"):
                res.update({"group_id": move_to_copy.group_id.id})
        return res
