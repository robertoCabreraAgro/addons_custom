from odoo import _, api, models
from odoo.exceptions import MissingError, UserError

from .. import fields as geo_fields

DEFAULT_EXTENT = (
    "-123164.85222423, 5574694.9538936, " "1578017.6490538, 6186191.1800898"
)


class Base(models.AbstractModel):
    """Extend Base class to allow definition of geo fields.

    This abstract model extends the base Odoo model to provide geographic
    functionality including geo field support, map view integration, and
    spatial data handling capabilities.
    """

    _inherit = "base"

    # Array of ash that define layer and data to use
    _georepr = []

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        """Add geo_type definition for geo fields.

        Extends the base fields_get method to include geometric field information
        for fields that start with 'geo_' type. This metadata is used by the
        frontend to properly render and handle geometric fields.

        Args:
            allfields (list, optional): List of field names to retrieve.
            attributes (list, optional): List of attributes to include.

        Returns:
            dict: Field definitions with added geo_type information for geometric fields.
        """
        res = super().fields_get(allfields=allfields, attributes=attributes)
        for f_name in res:
            field = self._fields.get(f_name)
            if field and field.type.startswith("geo_"):
                geo_type = {
                    "type": field.type,
                    "dim": int(field.dim),
                    "srid": field.srid,
                    "geo_type": field.geo_type,
                }
                # TODO
                if field.compute or field.related:
                    if not field.dim:
                        geo_type["dim"] = 2
                    if not field.srid:
                        geo_type["srid"] = 3857
                res[f_name]["geo_type"] = geo_type
        return res

    @api.model
    def _get_geo_view(self):
        """Retrieve the GeoEngine view for the current model.

        Searches for a geoengine type view associated with the current model.
        This view is required for geographic data visualization and interaction.

        Returns:
            ir.ui.view: The GeoEngine view record.

        Raises:
            UserError: When no GeoEngine view is found for the model.
        """
        IrView = self.env["ir.ui.view"]
        geo_view = IrView.sudo().search(
            [("model", "=", self._name), ("type", "=", "geoengine")],
            limit=1,
        )
        if not geo_view:
            raise UserError(
                _(
                    "No GeoEngine view defined for the model %s. \
                        Please create a view or modify view mode"
                )
                % self._name,
            )
        return geo_view

    @api.model
    def get_geoengine_layers(self, view_id=None, view_type="geoengine", **options):
        """Get GeoEngine layer configuration for map visualization.

        Retrieves background raster layers and active vector layers configuration
        for the GeoEngine map view, including projection settings and map extents.

        Args:
            view_id (int, optional): Specific view ID to use. If None, uses default geo view.
            view_type (str): Type of view, defaults to 'geoengine'.
            **options: Additional options for layer configuration.

        Returns:
            dict: Dictionary containing:
                - backgrounds: List of raster layer configurations
                - actives: List of vector layer configurations
                - projection: Map projection settings
                - restricted_extent: Map extent restrictions
                - default_extent: Default map extent
                - default_zoom: Default zoom level
        """
        view_obj = self.env["ir.ui.view"]

        if not view_id:
            view = self._get_geo_view()
        else:
            view = view_obj.browse(view_id)
        geoengine_layers = {
            "backgrounds": [],
            "actives": [],
            "projection": view.projection,
            "restricted_extent": view.restricted_extent,
            "default_extent": view.default_extent or DEFAULT_EXTENT,
            "default_zoom": view.default_zoom,
        }

        for layer in view.raster_layer_ids:
            layer_dict = layer.read()[0]
            geoengine_layers["backgrounds"].append(layer_dict)
        for layer in view.vector_layer_ids:
            layer_dict = layer.read()[0]
            layer_dict["attribute_field_id"] = self.set_field_real_name(
                layer_dict.get("attribute_field_id", False)
            )
            layer_dict["geo_field_id"] = self.set_field_real_name(
                layer_dict.get("geo_field_id", False)
            )
            layer_dict["resModel"] = layer._name
            layer_dict["model"] = layer.model_id.model
            layer_dict["model_domain"] = layer.model_domain
            geoengine_layers["actives"].append(layer_dict)
        return geoengine_layers

    @api.model
    def get_edit_info_for_geo_column(self, column):
        """Get editing configuration for a geometric field.

        Provides the necessary configuration for editing geometric data,
        including raster layer for drawing context and spatial reference information.

        Args:
            column (str): Name of the geometric field to get edit info for.

        Returns:
            dict: Dictionary containing:
                - edit_raster: Raster layer configuration for editing
                - srid: Spatial Reference System Identifier
                - projection: Map projection
                - restricted_extent: Map extent restrictions
                - default_extent: Default map extent
                - default_zoom: Default zoom level

        Raises:
            ValueError: When column doesn't exist or is not a geo field.
            MissingError: When no raster layer is found for the view.
        """
        raster_obj = self.env["geoengine.raster.layer"]

        field = self._fields.get(column)
        if not field or not isinstance(field, geo_fields.GeoField):
            raise ValueError(
                _("%s column does not exists or is not a geo field") % column
            )
        view = self._get_geo_view()
        raster = raster_obj.search(
            [("view_id", "=", view.id), ("use_to_edit", "=", True)], limit=1
        )
        if not raster:
            raster = raster_obj.search([("view_id", "=", view.id)], limit=1)
        if not raster:
            raise MissingError(_("No raster layer for view %s") % (view.name,))
        return {
            "edit_raster": raster.read()[0],
            "srid": field.srid,
            "projection": view.projection,
            "restricted_extent": view.restricted_extent,
            "default_extent": view.default_extent or DEFAULT_EXTENT,
            "default_zoom": view.default_zoom,
        }

    @api.model
    def set_field_real_name(self, in_tuple):
        """Convert field tuple to include real field name.

        Transforms a field reference tuple by replacing the field ID with
        the actual field name for easier processing.

        Args:
            in_tuple (tuple): Tuple containing (field_id, display_name, value).

        Returns:
            tuple: Modified tuple with (field_id, real_name, display_name) or
                   original tuple if input is falsy.
        """
        field_obj = self.env["ir.model.fields"]
        if not in_tuple:
            return in_tuple
        name = field_obj.browse(in_tuple[0]).name
        out = (in_tuple[0], name, in_tuple[1])
        return out
