from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import timedelta

class EstatePropertyOffer(models.Model):
    _name = 'estate.property.offer'
    _description = 'Real Estate Property Offer'
    _order = 'price desc'

    price = fields.Float(required=True)
    status = fields.Selection(
        selection=[('accepted', 'Accepted'), ('refused', 'Refused')],
        copy=False
    )
    partner_id = fields.Many2one('res.partner')
    validity = fields.Integer(default=7)
    date_deadline= fields.Date(
        string = "Deadline",
        compute = "_compute_date_deadline",
        inverse = "_inverse_date_deadline",
        store = True,
    )
    property_id = fields.Many2one('estate.property')

    # Constrain que evita números negativos
    _sql_constraints = [
        ('check_price_positive', 'CHECK(price >= 0)', 'Offer price must be strictly positive.'),
        ('check_validity_positive', 'CHECK(validity >= 0)', 'Validity must be positive.'),
    ]

    # Calcula la fecha límite por medio de los dias de validez que colocamos en nuestra variable vality
    @api.depends('create_date', 'validity')
    def _compute_date_deadline(self):
        for offer in self:
            if offer.create_date:
                offer.date_deadline = (offer.create_date.date() + timedelta(days=offer.validity))
            else: 
                offer.date_deadline = fields.Date.today() + timedelta(days=offer.validity)

    # Calcula los días cuando se movió manualmemnte en el calendario.
    def _inverse_date_deadline(self):
        for offer in self:
            if offer.create_date and offer.date_deadline:
                offer.validity = (offer.date_deadline - offer.create_date.date()).days

    # La oferta no puede ser menor al 90% de su valor
    @api.constrains('price', 'property_id')
    def _check_offer_price(self):
        for offer in self:
            if offer.price <= 0:
                raise UserError("Offer price must be strictly positive.")
            if offer.property_id and offer.property_id.expected_price > 0:
                min_offer = offer.property_id.expected_price * 0.9
                if offer.price < min_offer:
                    raise UserError(f"Offer must be at least 90% of expected price ({min_offer:.2f})")
                
    # El precio de la oferta se ajusta al 95% del precio esperado automáticamente aunque se puede  colocar de manera manual.
    @api.onchange('property_id')
    def _onchange_property_id(self):
        if self.property_id:
            self.price = self.property_id.expected_price * 0.95

    @api.model
    def create(self, vals):
        offer = super().create(vals)
        if offer.property_id and offer.property_id.state == 'new':
            offer.property_id.state = 'offer_received'
        return offer
    
    # ANALIZAR ESTE FRAGMENTO HASTA EL FINAL

    def action_accept_offer(self):
        for offer in self:
            if offer.status in ['accepted', 'refused']:
                raise UserError("This offer has already been accepted or refused.")
            if offer.property_id.has_accepted_offer:
                raise UserError("This property already has an accepted offer.")
            offer.status = 'accepted'
            offer.property_id.state = 'offer_accepted'
            offer.property_id.selling_price = offer.price
            offer.property_id.buyer_id = offer.partner_id

    def action_refuse_offer(self):
        for offer in self:
            if offer.status in ['accepted', 'refused']:
                raise UserError("This offer has already been accepted or refused.")
            offer.status = 'refused'