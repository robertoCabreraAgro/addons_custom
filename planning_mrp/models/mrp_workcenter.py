from odoo import fields, models


class MrpWorkcenter(models.Model):
    _inherit = 'mrp.workcenter'

    planning_slot_count = fields.Integer(
        string='Planning Slot Count',
        compute='_compute_planning_slot_count'
    )
    planning_slot_ids = fields.One2many(
        'planning.slot',
        'workcenter_id',
        string='Planning Slots'
    )

    def _compute_planning_slot_count(self):
        for workcenter in self:
            workcenter.planning_slot_count = len(workcenter.planning_slot_ids)

    def action_planning_action_workcenter_schedule(self):
        """
        Opens the planning schedule view filtered by the current work center.

        This server action retrieves the planning view and configures it to display
        only the planning slots related to the work center from which the action was called.
        """
        self.ensure_one()
        action = self.env.ref('planning_mrp.action_planning_slot_by_workcenter').read()[0]

        action['domain'] = [('workcenter_id', '=', self.id)]

        action['context'] = {
            'default_workcenter_id': self.id,
            'search_default_workcenter_id': self.id,
            **self.env.context
        }
        return action
