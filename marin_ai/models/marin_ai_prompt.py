from odoo import models, fields, api


class MarinAiPrompt(models.Model):
    """AI Prompt model for preserving the prompt history."""

    _name = "marin.ai.prompt"
    _description = "Marin AI Prompt"

    name = fields.Char(string="Name", required=True)
    prompt = fields.Text(string="Prompt")
    response = fields.Text(string="Response")
    prompt_template_id = fields.Many2one("marin.ai.prompt.template", string="Prompt Template")
    user = fields.Many2one("res.users", string="User")
    agent_id = fields.Many2one("marin.ai.agent", string="Agent")

    @api.model
    def create(self, vals):
        """Override create to auto-generate sequence number for name."""
        if not vals.get("name"):
            # Try to get sequence, fallback to timestamp-based name
            sequence_name = self.env["ir.sequence"].sudo().next_by_code("marin.ai.prompt")
            if sequence_name:
                vals["name"] = sequence_name
            else:
                # Generate more descriptive fallback name with timestamp and user info
                timestamp = fields.Datetime.now().strftime("%Y%m%d-%H%M%S")
                user_login = self.env.user.login or "user"
                # Take first part of email or username for brevity
                user_short = user_login.split('@')[0] if '@' in user_login else user_login
                vals["name"] = f"AI-{timestamp}-{user_short}"
                
        return super().create(vals)
