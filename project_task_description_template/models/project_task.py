# Copyright 2023 - Jarsa
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    description_template_id = fields.Many2one(
        "project.task.description.template", store=False
    )

    @api.onchange("description_template_id")
    def _onchange_description_template_id(self):
        if self.description_template_id:
            description = self.description if self.description else ""
            self.description = description + self.description_template_id.description

    def action_print_task_report(self):
        """
        Action to print task report
        Generates a PDF report for the current task
        """
        self.ensure_one()

        # Generate report
        return self.env.ref('project_task_description_template.action_project_task_report').report_action(self)

    def get_report_filename(self):
        """
        Generate filename for the PDF report
        Format: Reporte_[task_name]_[date].pdf
        """
        lang = self.env.user.lang or 'en_US'
        lang_obj = self.env['res.lang']._lang_get(lang)
        date_format = lang_obj.date_format
        current_date = fields.Date.today().strftime(date_format)
        task_name = self.name.replace(' ', '_').replace('/', '-')[:50] if self.name else 'Tarea'
        return f"Reporte_{task_name}_{current_date}"
