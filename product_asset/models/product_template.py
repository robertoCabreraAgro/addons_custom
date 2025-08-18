from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    asset_type = fields.Selection(
        selection=[
            ("equipment", "Equipment"),
            ("machinery", "Machinery"),
            ("product", "Product"),
            ("property", "Property"),
            ("vehicle", "Vehicle"),
        ],
        default="product",
    )

    # Technical fields
    power = fields.Integer(
        string="Power",
        help="Power in kW of the vehicle",
    )
    power_uom_name = fields.Char(
        string="Power unit of measure label",
        compute="_compute_power_uom_name",
    )
    co2 = fields.Float(
        string="CO2 Emissions",
        help="CO2 emissions of the vehicle",
    )
    fuel_efficiency_theoretical = fields.Float(
        aggregator="avg",
        help="Fuel efficiency in kilometers per liter (km/L)",
    )
    fuel_efficiency_min = fields.Float(
        aggregator="avg",
        help="Fuel efficiency in kilometers per liter (km/L)",
    )
    fuel_efficiency_max = fields.Float(
        aggregator="avg",
        help="Fuel efficiency in kilometers per liter (km/L)",
    )
    fuel_efficiency_uom_name = fields.Char(
        string="Fuel efficiency unit of measure label",
        compute="_compute_fuel_efficiency_uom_name",
    )
    fuel_tank_capacity = fields.Integer(
        string="Tank capacity",
        aggregator="avg",
        help="Fuel tank capacity in liters",
    )
    range = fields.Float(string="Range")
    weight_capacity = fields.Float(
        string="Max Weight",
    )
    weight_capacity_uom_name = fields.Char(
        string="Weight unit of measure label",
        compute="_compute_weight_capacity_uom_name",
    )
    volume_capacity = fields.Float(
        string="Max Volume",
    )
    volume_capacity_uom_name = fields.Char(
        string="Volume unit of measure label",
        compute="_compute_volume_capacity_uom_name",
    )
    doors = fields.Integer(
        string="Doors Number",
        help="Number of doors of the vehicle",
    )
    seats = fields.Integer(
        string="Seats Number",
        help="Number of seats of the vehicle",
    )
    count_lot_ids = fields.Integer(
        compute="_compute_count_lot_ids",
        string="Lots Count",
    )

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    def _compute_power_uom_name(self):
        self.weight_capacity_uom_name = (
            self._get_power_uom_name_from_ir_config_parameter()
        )

    def _compute_fuel_efficiency_uom_name(self):
        self.weight_capacity_uom_name = (
            self._get_fuel_efficiency_name_from_ir_config_parameter()
        )

    def _compute_weight_capacity_uom_name(self):
        self.weight_capacity_uom_name = (
            self._get_weight_uom_name_from_ir_config_parameter()
        )

    def _compute_volume_capacity_uom_name(self):
        self.volume_capacity_uom_name = (
            self._get_volume_uom_name_from_ir_config_parameter()
        )

    def _compute_count_lot_ids(self):
        for template in self:
            template.count_lot_ids = template.env["stock.lot"].search_count(
                [
                    ("product_id", "in", template.product_variant_ids.ids),
                ]
            )

    # @api.depends("model_id")
    # def _compute_image_128(self):
    #     for product in self:
    #         if product.model_id:
    #             product.image_128 = product.manufacturer_id.image_128
    #         else:
    #             product.image_128 = product.image_1920
