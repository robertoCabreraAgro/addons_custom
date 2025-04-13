from odoo import fields, models


class TagsCategories(models.Model):
    """Inherit TagsCategories"""

    _inherit = "documents.tag"

    active = fields.Boolean(default=True)
