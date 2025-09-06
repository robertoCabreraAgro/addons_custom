import logging

from odoo import _, api, models
from odoo.exceptions import MissingError, UserError
from odoo.tools import SQL

from .. import fields as geo_fields
from ..geo_operators import GeoOperator

logger = logging.getLogger(__name__)

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

    # List of supported geo operators
    _GEO_OPERATORS = [
        "geo_greater",
        "geo_lesser",
        "geo_equal",
        "geo_touch",
        "geo_within",
        "geo_contains",
        "geo_intersect",
    ]

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

    def _process_geo_operator(self, field_name, operator, value):
        """Process a single geo operator and return matching record IDs.

        Args:
            field_name (str): Name of the geo field.
            operator (str): Geo operator name.
            value: Value to compare against.

        Returns:
            set: Set of matching record IDs, or None if not a geo operation.
        """
        field = self._fields.get(field_name)
        if not field or not isinstance(field, geo_fields.GeoField):
            return None

        try:
            geo_operator = GeoOperator(field)
            table = self._table
            params = []

            # Map operator to SQL generation method
            operator_methods = {
                "geo_greater": geo_operator.get_geo_greater_sql,
                "geo_lesser": geo_operator.get_geo_lesser_sql,
                "geo_equal": geo_operator.get_geo_equal_sql,
                "geo_touch": geo_operator.get_geo_touch_sql,
                "geo_within": geo_operator.get_geo_within_sql,
                "geo_contains": geo_operator.get_geo_contains_sql,
                "geo_intersect": geo_operator.get_geo_intersect_sql,
            }

            method = operator_methods.get(operator)
            if not method:
                return None

            sql_condition = method(table, field_name, value, params)

            # Execute spatial query with safe parameterization
            query = SQL(
                "SELECT id FROM %s WHERE %s", SQL.identifier(table), SQL(sql_condition)
            )
            self.env.cr.execute(query, params)
            result_ids = [row[0] for row in self.env.cr.fetchall()]
            return set(result_ids)

        except Exception as e:
            logger.warning(
                "Failed to process geo operator %s on field %s: %s",
                operator,
                field_name,
                e,
            )
            return set()  # Return empty set for failed operations

    def _split_geo_domain(self, domain):
        """Split domain into geo and non-geo conditions.

        Args:
            domain (list): Search domain to split.

        Returns:
            tuple: (geo_conditions, regular_domain)
        """
        geo_conditions = []
        regular_domain = []

        for condition in domain:
            if (
                isinstance(condition, (list, tuple))
                and len(condition) == 3
                and condition[1] in self._GEO_OPERATORS
            ):
                geo_conditions.append(condition)
            else:
                regular_domain.append(condition)

        return geo_conditions, regular_domain

    @api.model
    def search(self, domain, offset=0, limit=None, order=None):
        """Override search to handle geo operators."""
        # Quick check for geo operators
        has_geo_ops = any(
            isinstance(cond, (list, tuple))
            and len(cond) == 3
            and cond[1] in self._GEO_OPERATORS
            for cond in domain
        )

        if not has_geo_ops:
            return super().search(domain, offset=offset, limit=limit, order=order)

        # Split domain into geo and regular conditions
        geo_conditions, regular_domain = self._split_geo_domain(domain)

        # Process geo conditions
        geo_results = []
        for field_name, operator, value in geo_conditions:
            result = self._process_geo_operator(field_name, operator, value)
            if result is not None:
                geo_results.append(result)
            else:
                # Not a valid geo field, treat as regular condition
                regular_domain.append([field_name, operator, value])

        # Get base results from standard domain
        # IMPORTANT: Cannot apply offset/limit here as geo filtering happens after
        # TODO: Optimize by integrating geo queries into SQL WHERE clause
        if regular_domain:
            # Fetch all matching records for intersection with geo results
            base_records = super().search(regular_domain, order=order)
        else:
            base_records = super().search([], order=order)

        # Combine results
        if geo_results:
            # Start with base query results
            final_ids = set(base_records.ids)

            # Intersect with each geo condition result
            for geo_result_set in geo_results:
                final_ids = final_ids.intersection(geo_result_set)

            # Convert to recordset and reapply ordering
            if final_ids:
                # Use search to get properly ordered recordset with offset/limit
                final_domain = [("id", "in", list(final_ids))]
                if regular_domain:
                    final_domain = ["&"] + final_domain + regular_domain
                result_records = super().search(
                    final_domain, offset=offset, limit=limit, order=order
                )
            else:
                result_records = self.browse()

            return result_records

        # Apply offset/limit/order when no geo filtering needed
        if regular_domain:
            return super().search(
                regular_domain, offset=offset, limit=limit, order=order
            )
        else:
            return super().search([], offset=offset, limit=limit, order=order)
