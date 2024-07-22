from odoo import api, fields, models
from odoo.tools import get_lang, SQL


class Task(models.Model):
    _inherit = "project.task"


    name = fields.Char(translate=True)

    #Override enterprise method
    @api.depends('planned_date_begin', 'depend_on_ids.date_deadline')
    def _compute_dependency_warning(self):
        if not self._origin:
            self.dependency_warning = False
            return

        self.flush_model(['planned_date_begin', 'date_deadline'])
        query = """
            SELECT t1.id,
                   ARRAY_AGG(t2.name) as depends_on_names
              FROM project_task t1
              JOIN task_dependencies_rel d
                ON d.task_id = t1.id
              JOIN project_task t2
                ON d.depends_on_id = t2.id
             WHERE t1.id IN %s
               AND t1.planned_date_begin IS NOT NULL
               AND t2.date_deadline IS NOT NULL
               AND t2.date_deadline > t1.planned_date_begin
          GROUP BY t1.id
	    """
        self._cr.execute(query, (tuple(self.ids),))
        lang = get_lang(self.env)
        depends_on_names_for_id = {
            group['id']: group['depends_on_names'].get(lang)
            for group in self._cr.dictfetchall()
        }
        for task in self:
            depends_on_names = depends_on_names_for_id.get(task.id)
            task.dependency_warning = depends_on_names and _(
                'This task cannot be planned before Tasks %s, on which it depends.',
                ', '.join(depends_on_names)
            )
