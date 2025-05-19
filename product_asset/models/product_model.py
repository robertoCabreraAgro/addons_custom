from odoo import _, api, fields, models
from odoo.osv import expression


FUEL_TYPES = [
    ("diesel", "Diesel"),
    ("gasoline", "Gasoline"),
    ("full_hybrid", "Full Hybrid"),
    ("plug_in_hybrid_diesel", "Plug-in Hybrid Diesel"),
    ("plug_in_hybrid_gasoline", "Plug-in Hybrid Gasoline"),
    ("cng", "CNG"),
    ("lpg", "LPG"),
    ("hydrogen", "Hydrogen"),
    ("electric", "Electric"),
]


class ProductModel(models.Model):
    _name = "product.model"
    _description = "Model of a product"
    _inherit = ["avatar.mixin"]
    _order = "name asc"

    name = fields.Char(
        "Model name",
        required=True,
        tracking=True,
    )
    active = fields.Boolean(default=True)
    manufacturer_id = fields.Many2one(
        comodel_name="res.partner",
        string="Manufacturer",
        required=True,
        tracking=True,
    )
    image_128 = fields.Image(
        related="manufacturer_id.image_128",
        readonly=True,
    )
    asset_type = fields.Selection(
        selection=[
            ("machinery", "Machinery"),
            ("product", "Product"),
            ("property", "Property"),
            ("vehicle", "Vehicle"),
        ],
        required=True,
        default="product",
        tracking=True,
    )
    transmission = fields.Selection(
        [
            ("manual", "Manual"),
            ("automatic", "Automatic"),
        ],
        string="Transmission",
        tracking=True,
    )
    fuel_type = fields.Selection(
        FUEL_TYPES,
        string="Fuel Type",
        default="electric",
        tracking=True,
    )
    doors = fields.Integer(
        string="Doors Number",
        tracking=True,
    )
    seats = fields.Integer(
        string="Seats Number",
        tracking=True,
    )
    fuel_tank_capacity = fields.Integer(
        string="Tank capacity",
        help="Fuel tank capacity in liters",
    )
    cilinders = fields.Integer(
        string="Cilinders Number",
    )
    fuel_efficiency = fields.Float(
        help="Fuel efficiency in kilometers per liter (km/L)"
    )
    power_unit = fields.Selection(
        selection=[
            ("power", "kW"),
            ("horsepower", "Horsepower"),
        ],
        string="Power Unit",
        required=True,
        default="power",
    )
    power = fields.Integer(
        string="Power",
        tracking=True,
    )
    co2 = fields.Float(
        "CO2 Emissions",
        tracking=True,
    )
    model_year = fields.Integer(
        tracking=True,
    )
    color = fields.Char(
        tracking=True,
    )
    vehicle_range = fields.Integer(
        string="Range",
    )
    weight_capacity = fields.Float(
        string="Max Weight",
    )
    volume_capacity = fields.Float(
        string="Max Volume",
    )
    trailer_hook = fields.Boolean(
        string="Trailer Hitch",
        default=False,
        tracking=True,
    )
    vehicle_count = fields.Integer(
        compute="_compute_product_count",
        search="_search_product_count",
    )

    def _compute_product_count(self):
        group = self.env["product.template"]._read_group(
            [("model_id", "in", self.ids)],
            ["model_id"],
            ["__count"],
        )
        count_by_model = {model.id: count for model, count in group}
        for model in self:
            model.vehicle_count = count_by_model.get(model.id, 0)

    @api.depends("manufacturer_id")
    def _compute_display_name(self):
        for record in self:
            name = record.name
            if record.manufacturer_id.name:
                name = f"{record.manufacturer_id.name}/{name}"
            record.display_name = name

    @api.model
    def _search_display_name(self, operator, value):
        if operator in expression.NEGATIVE_TERM_OPERATORS:
            positive_operator = expression.TERM_OPERATORS_NEGATION[operator]
        else:
            positive_operator = operator
        domain = expression.OR(
            [
                [("name", positive_operator, value)],
                [("manufacturer_id.name", positive_operator, value)],
            ]
        )
        if positive_operator != operator:
            domain = ["!", *domain]
        return domain

    @api.model
    def _search_product_count(self, operator, value):
        if operator not in ["=", "!=", "<", ">"] or not isinstance(value, int):
            raise NotImplementedError(_("Operation not supported."))

        fleet_models = self.env["product.model"].search([])
        if operator == "=":
            fleet_models = fleet_models.filtered(lambda m: m.vehicle_count == value)
        elif operator == "!=":
            fleet_models = fleet_models.filtered(lambda m: m.vehicle_count != value)
        elif operator == "<":
            fleet_models = fleet_models.filtered(lambda m: m.vehicle_count < value)
        elif operator == ">":
            fleet_models = fleet_models.filtered(lambda m: m.vehicle_count > value)
        return [("id", "in", fleet_models.ids)]

    def action_model_vehicle(self):
        self.ensure_one()
        context = {"default_model_id": self.id}
        if self.vehicle_count:
            name = _("Vehicles")
            view_mode = "kanban,list,form"
            context["search_default_model_id"] = self.id
        else:
            name = _("Vehicle")
            view_mode = "form"
        view = {
            "name": name,
            "type": "ir.actions.act_window",
            "res_model": "product.template",
            "view_mode": view_mode,
            "context": context,
        }
        return view
