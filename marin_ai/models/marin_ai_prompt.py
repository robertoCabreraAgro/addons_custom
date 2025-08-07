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
        """Override create to auto-generate sequence number for name based on agent."""
        if not vals.get("name") and vals.get("agent_id"):
            agent = self.env["marin.ai.agent"].browse(vals["agent_id"])
            sequence_code = f'marin.ai.prompt.{agent.name.lower().replace(" ", "_")}'
            vals["name"] = self.env["ir.sequence"].next_by_code(sequence_code)
        elif not vals.get("name"):
            vals["name"] = self.env["ir.sequence"].next_by_code("marin.ai.prompt")
        return super(MarinAiPrompt, self).create(vals)
