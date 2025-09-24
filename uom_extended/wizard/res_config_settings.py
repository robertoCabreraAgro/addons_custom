from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    product_length_in_yd = fields.Selection(
        selection=[
            ("0", "Meters"),
            ("1", "Yards"),
        ],
        string="Length unit of measure",
        default="0",
        config_parameter="product.length_in_yd",
    )
    product_odometer_in_mi = fields.Selection(
        selection=[
            ("0", "Kilometers"),
            ("1", "Miles"),
        ],
        string="Odometer unit of measure",
        default="0",
        config_parameter="product.odometer_in_mi",
    )
    product_area_in_square_ft = fields.Selection(
        selection=[
            ("0", "Square Meters"),
            ("1", "Square Feet"),
        ],
        string="Area unit of measure",
        default="0",
        config_parameter="product.area_in_square_ft",
    )
    product_power_in_hp = fields.Selection(
        selection=[
            ("0", "Kw"),
            ("1", "HP"),
        ],
        string="Power unit of measure",
        default="0",
        config_parameter="product.power_in_hp",
    )
    product_fuel_efficiency_in_mpg = fields.Selection(
        selection=[
            ("0", "Km/L"),
            ("1", "MPG"),
        ],
        string="Fuel efficiency unit of measure",
        default="0",
        config_parameter="product.fuel_efficiency_in_mpg",
    )
