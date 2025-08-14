from odoo import fields, models, _


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # ------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------

    power_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Power Unit",
        # default=lambda self: self.env.ref("uom.product_uom_kw").id,
        domain=lambda self: [
            (
                "id",
                "in",
                [
                    self.env.ref("product_asset.product_uom_wat").id,
                    self.env.ref("product_asset.product_uom_kw").id,
                    self.env.ref("product_asset.product_uom_mw").id,
                    self.env.ref("product_asset.product_uom_hp").id,
                ],
            ),
        ],
        copy=True,
        help="Odometer measure of the vehicle",
    )
    power = fields.Integer(
        string="Power",
        help="Power in kW of the vehicle",
    )
    odometer_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Odometer Unit",
        default=lambda self: self.env.ref("uom.product_uom_km").id,
        domain=lambda self: [
            (
                "id",
                "in",
                [
                    self.env.ref("uom.product_uom_km").id,
                    self.env.ref("uom.product_uom_mile").id,
                ],
            ),
        ],
        copy=True,
        help="Odometer unit of measure of the vehicle",
    )
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
    doors = fields.Integer(
        string="Doors Number",
        help="Number of doors of the vehicle",
    )
    seats = fields.Integer(
        string="Seats Number",
        help="Number of seats of the vehicle",
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
    fuel_tank_capacity = fields.Integer(
        string="Tank capacity",
        aggregator="avg",
        help="Fuel tank capacity in liters",
    )
    vehicle_range = fields.Float(string="Range")
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

    # ------------------------------------------------------------
    # COMPUTE METHODS
    # ------------------------------------------------------------

    def _compute_weight_capacity_uom_name(self):
        self.weight_capacity_uom_name = (
            self._get_weight_uom_name_from_ir_config_parameter()
        )

    def _compute_volume_capacity_uom_name(self):
        self.volume_capacity_uom_name = (
            self._get_volume_uom_name_from_ir_config_parameter()
        )

    # @api.depends("model_id")
    # def _compute_image_128(self):
    #     for product in self:
    #         if product.model_id:
    #             product.image_128 = product.manufacturer_id.image_128
    #         else:
    #             product.image_128 = product.image_1920
