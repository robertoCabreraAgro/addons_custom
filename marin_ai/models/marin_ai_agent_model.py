from odoo import models, fields, api
from odoo.exceptions import ValidationError
import base64
import os
from cryptography.fernet import Fernet


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
    api_key_encrypted = fields.Char(
        string="Encrypted API Key",
        help="Encrypted API key stored in database (optional, overrides environment variable)",
        groups="base.group_system",
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
                raise ValidationError(self.env._("Temperature must be between 0.0 and 1.0"))

    @api.constrains("max_tokens")
    def _check_max_tokens(self):
        """Validate max_tokens is positive."""
        for record in self:
            if record.max_tokens and record.max_tokens <= 0:
                raise ValidationError(self.env._("Max tokens must be a positive number"))

    @api.constrains("name", "provider")
    def _check_unique_model(self):
        """Ensure model name is unique per provider."""
        for record in self:
            domain = [
                ("name", "=", record.name),
                ("provider", "=", record.provider),
                ("id", "!=", record.id),
            ]
            if self.search_count(domain) > 0:
                raise ValidationError(
                    self.env._("A model with name '%s' already exists for provider '%s'")
                    % (record.name, record.provider)
                )

    def _get_encryption_key(self):
        """Get or create encryption key for API keys."""
        # Use system parameter to store encryption key
        key_param = self.env["ir.config_parameter"].sudo().get_param("marin_ai.encryption_key")

        if not key_param:
            # Generate new key
            key = Fernet.generate_key()
            key_b64 = base64.b64encode(key).decode()
            self.env["ir.config_parameter"].sudo().set_param("marin_ai.encryption_key", key_b64)
            return key
        else:
            return base64.b64decode(key_param.encode())

    def set_api_key(self, api_key):
        """Encrypt and store API key."""
        if not api_key:
            self.api_key_encrypted = False
            return

        key = self._get_encryption_key()
        cipher_suite = Fernet(key)
        encrypted_key = cipher_suite.encrypt(api_key.encode())
        self.api_key_encrypted = base64.b64encode(encrypted_key).decode()

    def get_api_key(self):
        """Decrypt and return API key."""
        # First try encrypted key from database
        if self.api_key_encrypted:
            try:
                key = self._get_encryption_key()
                cipher_suite = Fernet(key)
                encrypted_key = base64.b64decode(self.api_key_encrypted.encode())
                return cipher_suite.decrypt(encrypted_key).decode()
            except Exception:
                # Fall back to environment variable if decryption fails
                pass

        # Fall back to environment variable
        if self.api_key_env_var:
            return os.getenv(self.api_key_env_var)

        return None
