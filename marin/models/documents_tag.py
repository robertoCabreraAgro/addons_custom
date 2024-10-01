from odoo import fields, models


class TagsCategories(models.Model):
    _inherit = "documents.tag"

    active = fields.Boolean(default=True)
