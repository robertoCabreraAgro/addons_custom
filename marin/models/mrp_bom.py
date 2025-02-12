from odoo import fields, models


class MrpBom(models.Model):
    _inherit = 'mrp.bom'


    x_type = fields.Selection(
        [
            ('refill', 'Refill'),
            ('formulate', 'Formulate')
        ],
        'Marin Type',
    )
