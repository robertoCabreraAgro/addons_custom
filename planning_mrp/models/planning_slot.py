from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class PlanningSlot(models.Model):
    _name = "planning.slot"
    _inherit = ["planning.slot", "mail.thread"]
    _description = "Planning Slot with Mail Thread"

    state = fields.Selection(
        selection_add=[("cancelled", "Cancelled")],
        ondelete={"cancelled": "set default"},
    )

    workcenter_id = fields.Many2one(
        comodel_name="mrp.workcenter",
        string="Work Center",
        check_company=True,
        tracking=True,
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product to Manufacture",
        domain=[("bom_ids", "!=", False)],
        tracking=True,
    )

    @api.constrains("workcenter_id", "resource_id")
    def _check_company(self):
        for slot in self:
            if (
                slot.workcenter_id
                and slot.resource_id
                and slot.workcenter_id.company_id != slot.resource_id.company_id
            ):
                raise ValidationError(
                    _("Work center and employee must belong to the same company.")
                )

    def _get_planning_action(self, action_xml_id, domain):
        """
        Helper function to retrieve a planning action with the default project context
        and a specific domain.

        Args:
        action_xml_id (str): The XML ID of the action to retrieve (e.g., "planning_mrp.action_planning_slot_by_workcenter").
        domain (list): The domain to apply to the action.

        Returns:
        dict: A dictionary of the Odoo window action.
        """
        action = self.env.ref(action_xml_id).read()[0]
        project_id = self.env.company.planning_mrp_project_id.id

        if project_id:
            action["context"] = {"default_project_id": project_id, **self.env.context}

        action["domain"] = domain
        return action

    def get_action_planning_slot_by_resource(self):
        """Gets the planning action by resource."""
        return self.with_context(
            search_default_group_by_resource=True, show_planning_mrp=True
        )._get_planning_action(
            "planning_mrp.action_planning_slot_with_default_project",
            [("resource_id", "!=", False)],
        )

    def get_action_planning_slot_by_role(self):
        """Get the planning action by prole."""
        return self.with_context(
            search_default_group_by_role=True, show_planning_mrp=True
        )._get_planning_action(
            "planning_mrp.action_planning_slot_with_default_project",
            [("role_id", "!=", False)],
        )

    def get_action_planning_slot_by_workcenter(self):
        """Gets the planning action by work center."""
        return self.with_context(
            search_default_group_by_workcenter=True, show_planning_mrp=True
        )._get_planning_action(
            "planning_mrp.action_planning_slot_with_default_project",
            [("workcenter_id", "!=", False)],
        )

    def get_action_planning_slot_by_product(self):
        """Get the planning action by product."""
        return self.with_context(
            search_default_group_by_product=True, show_planning_mrp=True
        )._get_planning_action(
            "planning_mrp.action_planning_slot_with_default_project",
            [("product_id", "!=", False)],
        )
