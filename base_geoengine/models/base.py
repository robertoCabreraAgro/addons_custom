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
                        Please create a view or modify view type"
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
        if not view_id:
            view = self._get_geo_view()
        else:
            view = self.env["ir.ui.view"].browse(view_id)

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

    def _process_domain_with_geo(self, domain):
        """Process domain by converting geo operators to ID conditions.

        This method handles complex domains with logical operators (&, |, !)
        and converts geo operators into ('id', 'in', [...]) conditions that
        Odoo's ORM can handle natively.

        Args:
            domain (list): Search domain with potential geo operators.

        Returns:
            list: Processed domain with geo operators converted to ID filters.
        """
        if not domain:
            return domain

        result = []
        i = 0

        while i < len(domain):
            term = domain[i]

            # Handle logical operators
            if term == "&":
                result.append(term)
                i += 1
            elif term == "|":
                result.append(term)
                i += 1
            elif term == "!":
                result.append(term)
                i += 1
                # Process next term (which is being negated)
                if i < len(domain):
                    next_term = domain[i]
                    if self._is_geo_term(next_term):
                        # Convert negated geo operator
                        ids = self._process_geo_operator(
                            next_term[0], next_term[1], next_term[2]
                        )
                        if ids is not None:
                            result.append(("id", "not in", list(ids)))
                        else:
                            result.append(next_term)
                    else:
                        result.append(next_term)
                    i += 1
            # Handle leaf conditions
            elif self._is_geo_term(term):
                # Convert geo operator to ID filter
                field_name, operator, value = term
                ids = self._process_geo_operator(field_name, operator, value)
                if ids is not None:
                    result.append(("id", "in", list(ids)))
                else:
                    # Not a valid geo field, keep original term
                    result.append(term)
                i += 1
            else:
                # Regular condition, keep as-is
                result.append(term)
                i += 1

        return result

    @api.model
    def search(self, domain, offset=0, limit=None, order=None):
        """Override search to seamlessly handle geo operators.

        This implementation makes geo operators work exactly like regular operators.
        Developers can use them naturally in any domain expression:

        Examples:
            # Simple geo search
            self.search([('location', 'geo_within', polygon)])

            # Combined with regular operators
            self.search([
                ('active', '=', True),
                ('location', 'geo_intersect', area)
            ])

            # Complex domain with OR/AND
            self.search([
                '|',
                    ('location', 'geo_within', area1),
                    '&',
                        ('location', 'geo_intersect', area2),
                        ('type', '=', 'warehouse')
            ])

            # Negation works too
            self.search([
                '!', ('location', 'geo_within', restricted_area)
            ])
        """
        # Process domain to convert geo operators to ID filters
        processed_domain = self._process_domain_with_geo(domain)

        # Use standard search with processed domain
        return super().search(processed_domain, offset=offset, limit=limit, order=order)

    @api.model
    def search_count(self, domain):
        """Override search_count to handle geo operators.

        Examples:
            # Count locations in area
            count = self.search_count([('location', 'geo_within', polygon)])
        """
        processed_domain = self._process_domain_with_geo(domain)
        return super().search_count(processed_domain)

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """Override search_read to handle geo operators.

        Examples:
            # Get data for locations in area
            data = self.search_read(
                [('location', 'geo_intersect', area)],
                fields=['name', 'location']
            )
        """
        if domain:
            domain = self._process_domain_with_geo(domain)
        return super().search_read(
            domain=domain, fields=fields, offset=offset, limit=limit, order=order
        )

    def _is_geo_term(self, term):
        """Check if a domain term is a geo operator.

        Args:
            term: Domain term to check.

        Returns:
            bool: True if term is a geo operator.
        """
        return (
            isinstance(term, (list, tuple))
            and len(term) == 3
            and isinstance(term[1], str)
            and term[1] in self._GEO_OPERATORS
        )
