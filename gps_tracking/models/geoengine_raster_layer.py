from odoo import fields, models


class GeoengineRasterLayer(models.Model):
    _inherit = "geoengine.raster.layer"

    raster_type = fields.Selection(
        selection_add=[("xyz", "XYZ Tiles")], ondelete={"xyz": "set default"}
    )
