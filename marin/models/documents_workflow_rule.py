from odoo import fields, models


class WorkflowActionRule(models.Model):
    _inherit = "documents.workflow.rule"

    active = fields.Boolean(default=True)
