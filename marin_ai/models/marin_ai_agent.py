from odoo import models, fields, api


class MarinAiAgent(models.Model):
    """AI Agent model for managing AI agents in the system."""

    _name = 'marin.ai.agent'
    _description = 'Marin AI Agent'

    name = fields.Char(string='Name', required=True)
    agent_model_id = fields.Many2one('marin.ai.agent.model', string='Agent Model')
    context = fields.Text(string='Context')
    domain = fields.Many2many('ir.model', string='Domain Models', help='Models/tables that this agent can access')
    prompt_ids = fields.One2many('marin.ai.prompt', 'agent_id', string='Prompts')
