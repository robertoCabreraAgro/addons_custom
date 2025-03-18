from odoo import fields, models


class IrUIView(models.Model):
    _inherit = "ir.ui.view"

    type = fields.Selection(
        selection_add=[("geoengine", "GeoEngine")],
        ondelete={"geoengine": "cascade"},
    )

    raster_layer_ids = fields.One2many(
        "geoengine.raster.layer", "view_id", string="Raster layers", required=False
    )

    vector_layer_ids = fields.One2many(
        "geoengine.vector.layer", "view_id", string="Vector layers", required=True
    )

    projection = fields.Char(string="Projection", default="EPSG:3857", required=True)

    default_extent = fields.Char(
        string="Default map extent",
        default="-123164.85222423, 5574694.9538936, 1578017.6490538, 6186191.1800898",
    )

    default_zoom = fields.Integer(string="Default map zoom", default=5)
    restricted_extent = fields.Char(string="Restricted map extent")

    def _get_view_info(self):
        return {"geoengine": {"icon": "fa fa-map-o"}} | super()._get_view_info()

    def _is_qweb_based_view(self, view_type):
        if view_type == "geoengine":
            return True
        return super()._is_qweb_based_view(view_type)
