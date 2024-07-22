from odoo import fields, models


class DocumentFolder(models.Model):
    _inherit = "documents.folder"

    active = fields.Boolean(default=True)
