# Copyright 2023 - Jarsa
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    description_template_id = fields.Many2one(
        "project.task.description.template",
        store=True,
        domain="['|', ('project_ids', '=', False),('project_ids', 'in', (project_id))]",
    )

    @api.onchange("description_template_id")
    def _onchange_description_template_id(self):
        if self.description_template_id:
            description = self.description if self.description else ""
            self.description = description + self.description_template_id.description

    @api.onchange("project_id")
    def _onchange_project_id(self):
        """Method that clears the selected template when switching to a project to which this template is not associated."""
        if (
            self.project_id
            and self.description_template_id
            and self.project_id not in self.description_template_id.project_ids
        ):
            self.description_template_id = False
