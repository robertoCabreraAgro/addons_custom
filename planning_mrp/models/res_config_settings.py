from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    module_project = fields.Boolean(string="Project")
    planning_mrp_project_id = fields.Many2one(
        comodel_name="project.project",
        string="Default Project",
        related="company_id.planning_mrp_project_id",
        readonly=False,
    )
