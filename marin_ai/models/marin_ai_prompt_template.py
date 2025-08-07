from odoo import models, fields, api


class MarinAiPromptTemplate(models.Model):
    """AI Prompt Template model for managing reusable prompts."""

    _name = "marin.ai.prompt.template"
    _description = "Marin AI Prompt Template"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(string="Template Name", required=True, tracking=True)
    prompt = fields.Text(
        string="Prompt Template",
        required=True,
        tracking=True,
        help="Template with placeholders like {user_input}, {context}, etc.",
    )
    category = fields.Selection(
        [
            ("orchestrator", "Orchestrator"),
            ("inventory", "Inventory Agent"),
            ("sales", "Sales Agent"),
            ("chat", "Chat Agent"),
            ("final_response", "Final Response Formatter"),
            ("custom", "Custom"),
        ],
        string="Category",
        default="custom",
        tracking=True,
    )
    description = fields.Text(string="Description", help="Description of template purpose and usage")
    active = fields.Boolean(string="Active", default=True, tracking=True)

    # Usage tracking
    usage_count = fields.Integer(string="Usage Count", default=0, readonly=True)

    # Computed fields
    display_name = fields.Char(string="Display Name", compute="_compute_display_name", store=True)

    @api.depends("name", "category")
    def _compute_display_name(self):
        """Compute display name with category prefix."""
        for record in self:
            if record.category and record.category != "custom":
                record.display_name = f"[{record.category.title()}] {record.name}"
            else:
                record.display_name = record.name or "New Template"

    def action_view_usage(self):
        """Action to view usage statistics for this template."""
        self.ensure_one()
        return {
            'name': f'Usage Statistics - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'marin.ai.prompt',
            'view_mode': 'list,form',
            'domain': [('prompt_template_id', '=', self.id)],
            'context': {'search_default_template_id': self.id},
            'target': 'current',
        }
