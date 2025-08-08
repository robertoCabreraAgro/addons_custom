from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError


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
    def create(self, vals_list):
        """Override create to auto-generate sequence number for name."""
        if not isinstance(vals_list, list):
            vals_list = [vals_list]
        
        for vals in vals_list:
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
                    user_short = user_login.split("@")[0] if "@" in user_login else user_login
                    vals["name"] = f"AI-{timestamp}-{user_short}"

        return super().create(vals_list)

    def test_agent_prompt(self):
        """Test the agent with the provided prompt."""
        self.ensure_one()
        if not self.prompt:
            raise ValidationError("Please enter a prompt to test the agent.")

        if not self.agent_id:
            raise ValidationError("No agent selected for testing.")

        try:
            # Process the prompt through the agent
            response = self.agent_id.process_prompt_for_agent(self.prompt)

            # Update the response field
            self.write({"response": response})

            # Return the same form to show the response
            return {
                "type": "ir.actions.act_window",
                "res_model": "marin.ai.prompt",
                "res_id": self.id,
                "view_mode": "form",
                "view_id": self.env.ref("marin_ai.view_marin_ai_prompt_test_form").id,
                "target": "new",
                "context": self.env.context,
            }
        except Exception as e:
            raise UserError(f"Error testing agent: {str(e)}")
