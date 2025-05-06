from odoo import _, api, fields, models
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class StockLocation(models.Model):
    _inherit = "stock.location"

    block_outgoing = fields.Boolean(
        string="Block Outgoing",
        help="If checked, products cannot be moved out from this location "
             "unless the user belongs to the group that can force outgoing "
             "operations from blocked locations."
    )
    block_incoming = fields.Boolean(
        string="Block Incoming",
        help="If checked, products cannot be moved into this location "
             "unless the user belongs to the group that can force incoming "
             "operations to blocked locations."
    )


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def button_validate(self):
        """Override button_validate to check if any location is blocked."""
        self._check_blocked_locations()
        return super().button_validate()

    def _check_blocked_locations(self):
        """Check if any move line comes from/to a blocked location."""
        for picking in self:
            has_out_permission = self.env.user.has_group(
                'stock_blocked_location.group_stock_force_blocked_location_out'
            )
            has_in_permission = self.env.user.has_group(
                'stock_blocked_location.group_stock_force_blocked_location_in'
            )

            for move in picking.move_line_ids:
                out_blocked = move.location_id.block_outgoing
                in_blocked = move.location_dest_id.block_incoming

                if out_blocked and not has_out_permission:
                    raise UserError(_(
                        "Operation not allowed: attempting to move product FROM blocked location %s."
                    ) % move.location_id.display_name)

                if in_blocked and not has_in_permission:
                    raise UserError(_(
                        "Operation not allowed: attempting to move product TO blocked location %s."
                    ) % move.location_dest_id.display_name)

                if out_blocked and has_out_permission:
                    picking.message_post(
                        body=_("User %s confirmed OUTGOING from blocked location %s.") %
                            (self.env.user.name, move.location_id.display_name)
                    )
                if in_blocked and has_in_permission:
                    picking.message_post(
                        body=_("User %s confirmed INCOMING to blocked location %s.") %
                            (self.env.user.name, move.location_dest_id.display_name)
                    )


class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_done(self, cancel_backorder=False):
        """Override _action_done to check blocked locations."""
        for move in self:
            picking = move.picking_id
            if picking:
                picking._check_blocked_locations()
        return super()._action_done(cancel_backorder=cancel_backorder)