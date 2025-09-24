from lxml import etree

from odoo import api, fields, models
from odoo.fields import Domain
import odoo.orm.domains as orm_domains


class DateRangeSearchMixin(models.AbstractModel):
    """Mixin to add date range search capabilities to any model.

    This abstract model provides a technical search field that allows users to filter
    records by predefined date ranges. It automatically injects a date range selector
    into search views and translates date range selections into appropriate domain filters.

    The mixin works by:
    1. Adding a computed Many2one field to date.range
    2. Intercepting searches on this field and converting them to date comparisons
    3. Automatically injecting the field into search views

    To use this mixin:
    1. Inherit from 'date.range.search.mixin' in your model
    2. Set _date_range_search_field to your date field name
    3. The search field will be automatically available in search views

    Attributes:
        _date_range_search_field (str): Name of the date field to filter on.
                                        Defaults to 'date'. Override in your model.
        date_range_search_id (Many2one): Technical field for date range selection.

    Examples:
        >>> class SaleOrder(models.Model):
        ...     _name = 'sale.order'
        ...     _inherit = ['sale.order', 'date.range.search.mixin']
        ...     _date_range_search_field = 'date_order'
        ...
        >>> # Now users can search sales by fiscal year, quarter, etc.
        >>> # in the search view

        >>> class AccountMove(models.Model):
        ...     _name = 'account.move'
        ...     _inherit = ['account.move', 'date.range.search.mixin']
        ...     _date_range_search_field = 'date'
        ...
        >>> # Users can filter journal entries by predefined periods
    """

    _name = "date.range.search.mixin"
    _description = "Mixin class to add a Many2one style period search field"
    _date_range_search_field = "date"

    date_range_search_id = fields.Many2one(
        comodel_name="date.range",
        string="Filter by period (technical field)",
        compute="_compute_date_range_search_id",
        search="_search_date_range_search_id",
    )

    def _compute_date_range_search_id(self):
        """Compute method for the date range search field.

        This is a technical computed field that always returns False.
        The actual functionality is in the search method, not the compute.

        Note:
            This field exists only to provide a UI element for searching.
            The actual value is never stored or computed meaningfully.

        Examples:
            >>> order = self.env['sale.order'].browse(1)
            >>> order.date_range_search_id
            False
        """
        for record in self:
            record.date_range_search_id = False

    @api.model
    def _is_negative_operator(self, operator):
        """Check if the given operator is a negative/exclusion operator.

        This helper method determines if an operator like '!=', 'not in', 'not like'
        represents a negative condition that should exclude rather than include results.

        Args:
            operator (str): The operator to check (e.g., '=', '!=', 'in', 'not in').

        Returns:
            bool: True if the operator is negative, False otherwise.

        Examples:
            >>> self._is_negative_operator('!=')
            True
            >>> self._is_negative_operator('not in')
            True
            >>> self._is_negative_operator('=')
            False
            >>> self._is_negative_operator('in')
            False

        Note:
            Uses Odoo's NEGATIVE_CONDITION_OPERATORS constant from orm_domains.
        """
        return operator in orm_domains.NEGATIVE_CONDITION_OPERATORS

    @api.model
    def _search_date_range_search_id(self, operator, value):
        """Convert date range searches into date field domain filters.

        This search method intercepts searches on the date_range_search_id field
        and converts them into appropriate domain filters on the actual date field.

        Args:
            operator (str): The search operator (e.g., '=', '!=', 'in', 'not in').
            value: The value to search for. Can be:
                   - False/None: No filter
                   - True: All records
                   - str: Date range name to search
                   - int: Single date range ID
                   - list: Multiple date range IDs

        Returns:
            list or Domain: Domain expression to filter records by date range.

        Examples:
            >>> # Search for records in fiscal year 2024
            >>> fy2024 = self.env['date.range'].search([('name', '=', 'FY2024')])
            >>> domain = self._search_date_range_search_id('=', fy2024.id)
            >>> # Returns: [('&'), ('date', '>=', '2024-01-01'), ('date', '<=', '2024-12-31')]

            >>> # Search for records NOT in Q1 2024
            >>> q1 = self.env['date.range'].search([('name', '=', 'Q1 2024')])
            >>> domain = self._search_date_range_search_id('!=', q1.id)
            >>> # Returns domain excluding Q1 2024 dates

            >>> # Search by range name
            >>> domain = self._search_date_range_search_id('=', 'January 2024')
            >>> # Searches for range by name and returns appropriate domain

        Note:
            - Handles multiple ranges with OR logic
            - Properly handles negative operators
            - Returns Domain.TRUE/FALSE for edge cases
        """
        # Deal with some bogus values
        if not value:
            if self._is_negative_operator(operator):
                return Domain.TRUE
            return Domain.FALSE
        if value is True:
            if self._is_negative_operator(operator):
                return Domain.FALSE
            return Domain.TRUE
        # Assume from here on that the value is a string,
        # a single id or a list of ids
        ranges = self.env["date.range"]
        if isinstance(value, str):
            ranges = self.env["date.range"].search([("name", operator, value)])
        else:
            if isinstance(value, int):
                value = [value]
            sub_op = "not in" if self._is_negative_operator(operator) else "in"
            ranges = self.env["date.range"].search([("id", sub_op, value)])
        if not ranges:
            return Domain.FALSE
        domain = (len(ranges) - 1) * ["|"] + sum(
            (
                [
                    "&",
                    (self._date_range_search_field, ">=", date_range.date_start),
                    (self._date_range_search_field, "<=", date_range.date_end),
                ]
                for date_range in ranges
            ),
            [],
        )
        return domain

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        """Inject the date range search field into search views.

        This method overrides the standard get_view to automatically add the
        date_range_search_id field to search views if it wasn't explicitly added.

        The field is injected before the first group element in the search view,
        or at the end if no groups exist.

        Args:
            view_id (int, optional): ID of the view to retrieve.
            view_type (str): Type of view ('search', 'form', 'tree', etc.).
            **options: Additional options for view retrieval.

        Returns:
            dict: View definition with potentially modified arch for search views.

        Examples:
            >>> # Getting a search view will automatically include the date range field
            >>> view = self.env['sale.order'].get_view(view_type='search')
            >>> # The returned arch will contain:
            >>> # <field name="date_range_search_id" string="Period"/>

        Note:
            - Only modifies search views
            - Respects explicitly defined fields (doesn't duplicate)
            - Adds a separator before the field for visual clarity
        """
        result = super().get_view(view_id=view_id, view_type=view_type, **options)
        if view_type != "search":
            return result
        root = etree.fromstring(result["arch"])
        if root.xpath("//field[@name='date_range_search_id']"):
            # Field was inserted explicitely
            return result
        separator = etree.Element("separator")
        field = etree.Element(
            "field",
            attrib={
                "name": "date_range_search_id",
                "string": self.env._("Period"),
            },
        )
        groups = root.xpath("/search/group")
        if groups:
            groups[0].addprevious(separator)
            groups[0].addprevious(field)
        else:
            search = root.xpath("/search")
            search[0].append(separator)
            search[0].append(field)
        result["arch"] = etree.tostring(root, encoding="unicode")
        return result

    @api.model
    def get_views(self, views, options=None):
        """Customize the date range search field metadata in views.

        This method ensures the date range search field has a user-friendly label
        instead of showing the technical field name. This is particularly important
        for the Custom Filter dialog where users select fields.

        Args:
            views (list): List of (view_id, view_type) tuples to retrieve.
            options (dict, optional): Additional options for view retrieval.

        Returns:
            dict: View definitions with corrected field labels.

        Examples:
            >>> # The field will show as "Period" instead of "date_range_search_id"
            >>> views_data = self.env['sale.order'].get_views(
            ...     [(False, 'search'), (False, 'tree')]
            ... )
            >>> field_data = views_data['models']['sale.order']['fields']
            >>> field_data['date_range_search_id']['string']
            'Period'

        Note:
            - The technical name is preserved for the Export widget
            - Only the display string is changed for user interfaces
            - Translatable through the standard translation system
        """
        result = super().get_views(views, options=options)
        if "date_range_search_id" in result["models"][self._name]["fields"]:
            result["models"][self._name]["fields"]["date_range_search_id"]["string"] = (
                self.env._("Period")
            )
        return result
