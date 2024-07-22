from odoo import fields, models


class DocumentsFacet(models.Model):
    _inherit = "documents.facet"

    active = fields.Boolean(default=True)


class TagsCategories(models.Model):
    _inherit = "documents.tag"

    active = fields.Boolean(default=True)
