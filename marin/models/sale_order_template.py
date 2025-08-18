from odoo import models, fields, api
from odoo.exceptions import ValidationError


class SaleOrderTemplate(models.Model):
    """Extends sale.order.template to include agricultural season references.

    This extension allows linking quotation templates with specific agricultural
    seasons using date.range model with type 'AG', enabling seasonal sales
    management and objective setting based on crop cycles.
    """

    _inherit = "sale.order.template"

    season_id = fields.Many2one(
        "date.range",
        string="AG Season",
        domain="[('type_id.name', '=', 'AG')]",
        help="Select the agricultural season for this quotation template",
    )
    season_date_start = fields.Date(
        string="Season Start Date",
        related="season_id.date_start",
        readonly=True,
        help="Start date of the selected agricultural season",
    )
    season_date_end = fields.Date(
        string="Season End Date",
        related="season_id.date_end",
        readonly=True,
        help="End date of the selected agricultural season",
    )
