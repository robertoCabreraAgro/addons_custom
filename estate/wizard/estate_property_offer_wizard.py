from odoo import models, fields, api

class EstatePropertyOfferWizard(models.TransientModel):
    _name = 'estate.property.offer.wizard'
    _description = 'Create Multiple Offers Wizard'

    price = fields.Float(required=True)
    partner_id = fields.Many2one('res.partner', required=True, string='Customer')
    validity = fields.Integer(default=7, string="Validity (days)")

    def action_create_offers(self):
        self.ensure_one()
        active_ids = self.env.context.get('active_ids', [])
        properties = self.env['estate.property'].browse(active_ids)
        
        for property in properties:
            self.env['estate.property.offer'].create({
                'price': self.price,
                'partner_id': self.partner_id.id,
                'property_id': property.id,
                'validity': self.validity,
            })
        return {'type': 'ir.actions.act_window_close'}