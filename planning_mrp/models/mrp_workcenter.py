from odoo import fields, models, api
from datetime import datetime


class MrpWorkcenter(models.Model):
    _inherit = "mrp.workcenter"

    planning_slot_count = fields.Integer(
        string="Active Planning Slot Count",
        compute="_compute_planning_slot_count",
        help="Number of active and future planning slots for this workcenter",
    )
    planning_slot_ids = fields.One2many(
        "planning.slot", "workcenter_id", string="Planning Slots"
    )

    def _compute_planning_slot_count(self):
        """
        Compute count of active and future planning slots.
        Only counts slots where end_datetime is greater than current datetime.
        """
        for workcenter in self:
            current_datetime = fields.Datetime.now()
            active_slots = workcenter.planning_slot_ids.filtered(
                lambda slot: slot.end_datetime >= current_datetime
                and slot.state != "cancelled"
            )
            workcenter.planning_slot_count = len(active_slots)

    def action_planning_action_workcenter_schedule(self):
        """
        Opens the planning schedule view filtered by the current work center.

        This server action retrieves the planning view and configures it to display
        only the planning slots related to the work center from which the action was called.
        """
        self.ensure_one()
        action = self.env.ref(
            "planning_mrp.action_server_planning_slot_by_workcenter"
        ).read()[0]

        action["domain"] = [("workcenter_id", "=", self.id)]

        action["context"] = {
            "default_workcenter_id": self.id,
            "search_default_workcenter_id": self.id,
            **self.env.context,
        }
        return action
