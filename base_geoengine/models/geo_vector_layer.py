from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

SUPPORTED_ATT = [
    "float",
    "integer",
    "integer_big",
    "related",
    "function",
    "date",
    "datetime",
    "char",
    "text",
    "selection",
]

NUMBER_ATT = ["float", "integer", "integer_big"]


class GeoVectorLayer(models.Model):
    _name = "geoengine.vector.layer"
    _description = "Vector Layer"
    _order = "sequence ASC, name"

    name = fields.Char("Layer Name", translate=True, required=True)
    sequence = fields.Integer("Layer Priority", default=6)
    geo_repr = fields.Selection(
        selection=[
            ("basic", "Basic"),
            # Actually we have to think if we should separate it for colored
            ("proportion", "Proportional Symbol"),
            ("colored", "Colored range/Chroma.js"),
        ],
        string="Representation mode",
        required=True,
    )
    classification = fields.Selection(
        selection=[
            ("unique", "Unique value"),
            ("interval", "Interval"),
            ("quantile", "Quantile"),
            ("custom", "Custom"),
        ],
        string="Classification mode",
        required=False,
    )
    begin_color = fields.Char(
        string="Begin color class",
        required=False,
        help="hex value",
    )
    end_color = fields.Char(
        string="End color class",
        required=False,
        default="#FF680A",
        help="hex value",
    )
    nb_class = fields.Integer("Number of class", default=1)
    model_id = fields.Many2one(
        comodel_name="ir.model",
        string="Model to use",
        compute="_compute_model_id",
        store=True,
        readonly=False,
    )
    model_name = fields.Char(related="model_id.model", readonly=True)
    model_domain = fields.Char(default="[]")
    model_view_id = fields.Many2one(
        comodel_name="ir.ui.view",
        string="Model view",
        compute="_compute_model_view_id",
        readonly=False,
        domain=[("type", "=", "geoengine")],
    )
    view_id = fields.Many2one(
        comodel_name="ir.ui.view",
        string="Related View",
        required=True,
        domain=[("type", "=", "geoengine")],
    )
    geo_field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        string="Geo field",
        required=True,
        domain=[("ttype", "ilike", "geo_")],
        ondelete="cascade",
    )
    attribute_field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        string="Attribute field",
        domain=[("ttype", "in", SUPPORTED_ATT)],
    )
    readonly = fields.Boolean("Layer is read only")
    display_polygon_labels = fields.Boolean("Display Labels on Polygon")
    active_on_startup = fields.Boolean(
        help="Layer will be shown on startup if checked.",
    )
    layer_opacity = fields.Float(default=1.0)
    layer_transparent = fields.Boolean()

    @api.constrains("geo_field_id", "model_id")
    def _check_geo_field_id(self):
        """Validate that geo_field_id belongs to the specified model.

        Ensures the selected geometric field is actually a field of the
        model specified in model_id to prevent configuration errors.

        Raises:
            ValidationError: When geo_field_id model doesn't match model_id.
        """
        for rec in self:
            if rec.model_id:
                if not rec.geo_field_id.model_id == rec.model_id:
                    raise ValidationError(
                        _(
                            "The geo_field_id must be a field in %s model",
                            rec.model_id.display_name,
                        )
                    )

    @api.constrains("geo_repr", "attribute_field_id")
    def _check_geo_repr(self):
        """Validate geo representation configuration against attribute field type.

        Ensures that colored and proportional representations use numeric fields
        when required, preventing invalid visualization configurations.

        Raises:
            ValidationError: When non-numeric field is used with representations
                           requiring numeric data (colored/proportional).
        """
        for rec in self:
            if (
                rec.attribute_field_id
                and rec.attribute_field_id.ttype not in NUMBER_ATT
            ):
                if (
                    rec.geo_repr == "colored"
                    and rec.classification != "unique"
                    or rec.geo_repr == "proportion"
                ):
                    raise ValidationError(
                        _(
                            "You need to select a numeric field",
                        )
                    )

    @api.constrains("attribute_field_id", "geo_field_id")
    def _check_if_attribute_in_geo_field(self):
        """Validate that attribute_field_id belongs to the same model as geo_field_id.

        Ensures both fields are from the same model to prevent cross-model
        field references that would cause runtime errors.

        Raises:
            ValidationError: When fields belong to different models.
        """
        for rec in self:
            if rec.attribute_field_id and rec.geo_field_id:
                if rec.attribute_field_id.model != rec.geo_field_id.model:
                    raise ValidationError(
                        _(
                            "You need to provide an attribute that exists in %s model",
                            rec.geo_field_id.model_id.display_name,
                        )
                    )

    @api.depends("model_id")
    def _compute_model_view_id(self):
        """Compute the geoengine view associated with the selected model.

        Automatically finds and sets the geoengine view for the model_id,
        enabling proper layer configuration and visualization.
        """
        for rec in self:
            if rec.model_id:
                for view in rec.model_id.view_ids:
                    if view.type == "geoengine":
                        rec.model_view_id = view
            else:
                rec.model_view_id = ""

    @api.depends("geo_field_id", "view_id")
    def _compute_model_id(self):
        """Compute model_id based on geo_field_id and view_id relationship.

        Sets the model_id when geo_field belongs to a different model than
        the view, enabling cross-model layer configurations.
        """
        for rec in self:
            if rec.view_id and rec.geo_field_id:
                if rec.view_id.model != rec.geo_field_id.model:
                    rec.model_id = rec.geo_field_id.model_id
                else:
                    rec.model_id = ""
            else:
                rec.model_id = ""
