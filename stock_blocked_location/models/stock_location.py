from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockLocation(models.Model):
    _inherit = "stock.location"

    block_outgoing = fields.Boolean(
        string="Block Outgoing",
        help="If checked, products cannot be moved out from this location "
             "unless the user belongs to the group that can force outgoing "
             "operations from blocked locations."
    )


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def button_validate(self):
        """Override button_validate to check if any location is blocked."""
        self._check_blocked_locations()
        return super().button_validate()

    def _check_blocked_locations(self):
        """Check if any move line comes from a blocked location."""
        for picking in self:
            blocked_location_moves = picking.move_line_ids.filtered(
                lambda ml: ml.location_id.block_outgoing
            )
            if blocked_location_moves:
                has_permission = self.env.user.has_group(
                    'stock_blocked_location.group_stock_force_blocked_location'
                )
                if has_permission:
                    for move_line in blocked_location_moves:
                        picking.message_post(
                            body=_(
                                "The user %s has confirmed the outgoing "
                                "operation from the blocked location %s."
                            ) % (
                                self.env.user.name,
                                move_line.location_id.display_name
                            )
                        )
                else:
                    location_names = ", ".join(
                        blocked_location_moves.mapped('location_id.display_name')
                    )
                    raise UserError(_(
                        "You cannot validate this transfer because it contains "
                        "outgoing operations from blocked locations: %s"
                    ) % location_names)


class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_done(self, cancel_backorder=False):
        """Override _action_done to check blocked locations."""
        for move in self:
            picking = move.picking_id
            if picking:
                picking._check_blocked_locations()
        return super()._action_done(cancel_backorder=cancel_backorder)