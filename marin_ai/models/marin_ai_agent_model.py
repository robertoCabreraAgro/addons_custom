from odoo import models, fields, api


class MarinAiAgentModel(models.Model):
    """AI Agents Model for managing AI models configuration."""

    _name = 'marin.ai.agent.model'
    _description = 'Marin AI Agent Model'

    name = fields.Char(string='Name', required=True)
    api_key = fields.Char(string='API Key')
    temperature = fields.Float(string='Temperature')
