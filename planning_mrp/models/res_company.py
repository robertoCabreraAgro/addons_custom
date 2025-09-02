from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    planning_mrp_project_id = fields.Many2one("project.project") 
