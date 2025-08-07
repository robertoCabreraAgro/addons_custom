from odoo import models, fields, api
from odoo.exceptions import ValidationError


class MarinAiAgentModel(models.Model):
    """AI Agent Model for managing AI models configuration."""

    _name = "marin.ai.agent.model"
    _description = "Marin AI Agent Model"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        string="Model Name", required=True, tracking=True, help="Name of the AI model (e.g., gemini-1.5-flash)"
    )
    provider = fields.Selection(
        [
            ("google", "Google Gemini"),
            ("openai", "OpenAI"),
            ("anthropic", "Anthropic Claude"),
        ],
        string="Provider",
        default="google",
        required=True,
        tracking=True,
    )
    api_key_env_var = fields.Char(
        string="API Key Environment Variable",
        default="GEMINI_API_KEY",
        help="Environment variable name for API key",
        tracking=True,
    )
    temperature = fields.Float(
        string="Default Temperature",
        default=0.0,
        help="Default temperature setting for this model (0.0-1.0)",
        tracking=True,
    )
    max_tokens = fields.Integer(string="Max Tokens", help="Maximum tokens for responses")
    active = fields.Boolean(string="Active", default=True, tracking=True)
    description = fields.Text(string="Description", help="Description of model capabilities")

    # Computed fields
    display_name = fields.Char(string="Display Name", compute="_compute_display_name", store=True)

    @api.depends("name", "provider")
    def _compute_display_name(self):
        """Compute display name combining provider and model name."""
        for record in self:
            if record.provider and record.name:
                record.display_name = f"{record.provider.title()}: {record.name}"
            else:
                record.display_name = record.name or "New Model"

    @api.constrains("temperature")
    def _check_temperature(self):
        """Validate temperature is between 0 and 1."""
        for record in self:
            if record.temperature < 0.0 or record.temperature > 1.0:
                raise ValidationError("Temperature must be between 0.0 and 1.0")
