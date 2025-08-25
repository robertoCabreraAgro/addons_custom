from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    property_offers_ids = fields.One2many(
        'estate.property.offer', 
        'partner_id', 
        string='Property Offers'
    )