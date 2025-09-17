from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import timedelta

class EstateProperty(models.Model):
    _name = 'estate.property'
    _description = 'Real Estate Property'
    _order = 'id desc'

    # Campos básicos
    name = fields.Char(required=True)
    description = fields.Text()
    postcode = fields.Char()
    date_availability = fields.Date(
        copy=False, 
        default=lambda self: fields.Date.today() + timedelta(days=90)
    )
    expected_price = fields.Float(required=True)
    selling_price = fields.Float(copy=False)
    bedrooms = fields.Integer(default=2)
    living_area = fields.Integer()
    facades = fields.Integer()
    garage = fields.Boolean()
    garden = fields.Boolean()
    garden_area = fields.Integer()
    garden_orientation = fields.Selection(
        selection=[('north', 'North'),
                   ('south', 'South'),
                   ('east', 'East'),
                   ('west', 'West')]
    )    
    active = fields.Boolean(default=True)
    state = fields.Selection(
        selection=[
            ('new', 'New'), 
            ('offer_received', 'Offer Received'), 
            ('offer_accepted', 'Offer Accepted'), 
            ('sold', 'Sold'), 
            ('canceled', 'Canceled')
        ],
        default='new',
        required=True,
        copy=False
    )
    property_type_id = fields.Many2one('estate.property.type')
    buyer_id = fields.Many2one('res.partner', copy=False)
    salesperson_id = fields.Many2one(
        'res.users', default=lambda self: self.env.user
    )
    tag_ids = fields.Many2many('estate.property.tag')
    offer_ids = fields.One2many('estate.property.offer', 'property_id')

    # Campos computados
    total_area = fields.Float(compute='_compute_total_area', string='(sqm)')
    best_price = fields.Float(compute='_compute_offer_metrics', string='Best Offer')
    offer_count = fields.Integer(compute='_compute_offer_metrics')
    has_accepted_offer = fields.Boolean(compute='_compute_offer_metrics')
    show_garden_fields = fields.Boolean(compute="_compute_show_garden_fields")

    # Restricciones SQL
    _sql_constraints = [
        ('check_expected_price_positive','CHECK(expected_price >= 0)', 'Expected price must be strictly positive.'),
        ('check_selling_price_positive', 'CHECK(selling_price >= 0)', 'Selling price must be strictly positive.'),
        ('check_bedrooms_positive', 'CHECK(bedrooms >= 1)', 'Bedrooms must be positive.'),
    ]

    # Computación de áreas
    @api.depends('living_area', 'garden_area')
    def _compute_total_area(self):
        for record in self:
            record.total_area = record.living_area + record.garden_area

    # Computación de métricas de ofertas
    @api.depends('offer_ids.price', 'offer_ids.status')
    def _compute_offer_metrics(self):
        for record in self:
            prices = record.offer_ids.mapped('price')
            record.best_price = max(prices) if prices else 0.0
            record.offer_count = len(prices)
            record.has_accepted_offer = any(o.status == 'accepted' for o in record.offer_ids)

    # Campo booleano computado para mostrar/ocultar garden_area y garden_orientation
    @api.depends('garden')
    def _compute_show_garden_fields(self):
        for record in self:
            record.show_garden_fields = record.garden

    # Onchange method para vaciar garden_area y garden_orientation
    @api.onchange('garden')
    def _onchange_garden(self):
        for record in self:
            if record.garden:
                record.garden_area = 1
                record.garden_orientation = 'north'
            else:
                record.garden_area = 0
                record.garden_orientation = False

    # Restricciones Python (es para evitar que las ofertas sean menores al 90% sobre el precio de la propiedad)
    @api.constrains('selling_price', 'expected_price')
    def _check_selling_price(self):
        for record in self:
            if record.selling_price > 0:
                min_price = record.expected_price * 0.9
                if record.selling_price < min_price:
                    raise UserError(f"Selling price cannot be lower than 90% of expected price ({min_price:.2f})")

    # Métodos de acción
    def action_sold(self):
        for record in self:
            if record.state == 'canceled':
                raise UserError("Canceled properties cannot be sold.")
            if record.state == 'sold':
                raise UserError("Property is already sold")
            record.state = 'sold'
        return True

    def action_canceled(self):
        for record in self:
            if record.state == 'sold':
                raise UserError("Sold properties cannot be canceled.")
            record.state = 'canceled'
        return True

    def action_view_offers(self):
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Property Offers"),
            'res_model': 'estate.property.offer',
            'view_mode': 'list,form',
            'domain': [('property_id', '=', self.id)],
            'context': {'default_property_id': self.id}
        }
