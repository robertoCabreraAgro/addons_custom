from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PlanningSlot(models.Model):
    _name = "planning.slot"
    _inherit = ["planning.slot", "mail.thread"]
    _description = "Planning Slot with Mail Thread"

    state = fields.Selection(
        selection_add=[("cancelled", "Cancelled")],
        ondelete={"cancelled": "set default"},
    )

    cancel_details = fields.Text(string="Cancellation Details")
    cancel_date = fields.Datetime(string="Cancel date", readonly=True, copy=False)
    cancelled_by = fields.Many2one(
        comodel_name="res.users", string="Cancelled by", readonly=True, copy=False
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
    production_id = fields.Many2one(
        comodel_name="mrp.production",
        string="Manufacturing Order",
        tracking=True,
    )
    workorder_id = fields.Many2one(
        comodel_name="mrp.workorder",
        string="Work Order",
        tracking=True,
    )
    planning_manufacturing_project_id = fields.Many2one(
        comodel_name="project.project", string="Default Manufacturing Planning Project"
    )
    cancel_reason_id = fields.Many2one(
        comodel_name="planning.cancel.reason",
        string="Cancel Reason",
        tracking=True,
        ondelete="restrict",
    )
    can_be_cancelled = fields.Boolean(
        string="Can be Cancelled", compute="_compute_can_be_cancelled"
    )

    @api.depends("state", "end_datetime")
    def _compute_can_be_cancelled(self):
        """Compute if the slot can be cancelled based on state and date"""
        now = fields.Datetime.now()
        for slot in self:
            slot.can_be_cancelled = (
                slot.state == "published"
                and slot.end_datetime
                and slot.end_datetime >= now
            )

    @api.onchange("workorder_id")
    def _onchange_workorder_id(self):
        """Auto-complete workcenter, production and product when workorder is selected"""
        if self.workorder_id:
            self.workcenter_id = self.workorder_id.workcenter_id
            self.production_id = self.workorder_id.production_id
            self.product_id = self.workorder_id.production_id.product_id

    @api.constrains("state", "cancel_reason_id")
    def _check_cancel_reason_required(self):
        for record in self:
            if record.state == "cancelled" and not record.cancel_reason_id:
                raise ValidationError(
                    "A cancellation reason is required when the status is 'Canceled'."
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
        """Get the planning action by role."""
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
