from odoo import models, fields


class ResourceAsset(models.Model):
    _name = "resource.asset"
    _description = "Python scripts from Odoo interface"
    _inherit = ['mail.activity.mixin', 'resource.mixin']
    _order = 'name'
