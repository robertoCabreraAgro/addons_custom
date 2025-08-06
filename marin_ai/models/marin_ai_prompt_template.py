from odoo import models, fields, api


class MarinAiPromptTemplate(models.Model):
    """AI Prompt Template model for fast prompting."""

    _name = 'marin.ai.prompt.template'
    _description = 'Marin AI Prompt Template'

    name = fields.Char(string='Name', required=True)
    prompt = fields.Text(string='Prompt')
