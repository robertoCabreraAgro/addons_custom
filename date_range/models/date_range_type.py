import logging

from dateutil.relativedelta import relativedelta
from dateutil.rrule import DAILY, MONTHLY, WEEKLY, YEARLY

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DateRangeType(models.Model):
    """Date Range Type model for categorizing and managing date ranges.

    This model defines different types of date ranges (e.g., Fiscal Year, Quarter, Month)
    that can be used across the system. It provides:
    - Type categorization for date ranges
    - Autogeneration settings for automatic range creation
    - Naming templates for consistent range names
    - Company-specific configuration
    - Overlap validation rules

    Attributes:
        name (Char): The name of the date range type.
        allow_overlap (Boolean): Whether ranges of this type can overlap.
        active (Boolean): Whether this type is active.
        company_id (Many2one): The company this type belongs to.
        date_range_ids (One2many): All date ranges of this type.
        date_ranges_exist (Boolean): Whether any ranges of this type exist.
        name_expr (Text): Expression for generating range names.
        name_prefix (Char): Prefix for auto-generated range names.
        duration_count (Integer): Duration for each generated range.
        unit_of_time (Selection): Time unit for duration (years/months/weeks/days).
        autogeneration_date_start (Date): Start date for auto-generation.
        autogeneration_count (Integer): Number of periods to generate ahead.
        autogeneration_unit (Selection): Time unit for generation ahead.

    Examples:
        >>> # Create a fiscal year type
        >>> fiscal_year_type = self.env['date.range.type'].create({
        ...     'name': 'Fiscal Year',
        ...     'allow_overlap': False,
        ...     'duration_count': 1,
        ...     'unit_of_time': str(YEARLY),
        ...     'name_prefix': 'FY',
        ... })

        >>> # Create a quarterly type with auto-generation
        >>> quarter_type = self.env['date.range.type'].create({
        ...     'name': 'Quarter',
        ...     'allow_overlap': False,
        ...     'duration_count': 3,
        ...     'unit_of_time': str(MONTHLY),
        ...     'name_expr': "'Q%s %s' % ((date_start.month-1)//3 + 1, date_start.year)",
        ...     'autogeneration_count': 4,
        ...     'autogeneration_unit': str(YEARLY),
        ... })
    """

    _name = "date.range.type"
    _description = "Date Range Type"
    _order = "name,id"

    name = fields.Char(required=True, translate=True)
    allow_overlap = fields.Boolean(
        default=False,
        help="If set, date ranges of same type must not overlap.",
    )
    active = fields.Boolean(
        default=True,
        help="The active field allows you to hide the date range type "
        "without removing it.",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company.id,
        index=1,
    )
    date_range_ids = fields.One2many("date.range", "type_id", string="Ranges")
    date_ranges_exist = fields.Boolean(compute="_compute_date_ranges_exist")

    # Defaults for generating date ranges
    name_expr = fields.Text(
        "Range name expression",
        help=(
            "Evaluated expression. E.g. "
            "\"'FY%s' % date_start.strftime('%Y%m%d')\"\nYou can "
            "use the Date types 'date_end' and 'date_start', as well as "
            "the 'index' variable."
        ),
    )
    range_name_preview = fields.Char(compute="_compute_range_name_preview", store=True)
    name_prefix = fields.Char("Range name prefix")
    duration_count = fields.Integer("Duration")
    unit_of_time = fields.Selection(
        selection=[
            (str(YEARLY), "years"),
            (str(MONTHLY), "months"),
            (str(WEEKLY), "weeks"),
            (str(DAILY), "days"),
        ]
    )
    autogeneration_date_start = fields.Date(
        string="Autogeneration Start Date",
        help="Only applies when there are no date ranges of this type yet",
    )
    autogeneration_count = fields.Integer()
    autogeneration_unit = fields.Selection(
        selection=[
            (str(YEARLY), "years"),
            (str(MONTHLY), "months"),
            (str(WEEKLY), "weeks"),
            (str(DAILY), "days"),
        ]
    )

    _date_range_type_uniq = models.Constraint(
        "UNIQUE(name, company_id)",
        "A date range type must be unique per Company",
    )

    @api.constrains(
        "autogeneration_date_start",
        "autogeneration_count",
        "duration_count",
        "unit_of_time",
    )
    def _check_autogeneration_settings(self):
        """Validate autogeneration settings are consistent and complete.

        This constraint ensures that when autogeneration is configured, all required
        fields are properly set and have valid values.

        Raises:
            ValidationError: If autogeneration settings are incomplete or invalid:
                - Autogeneration date start is missing when count is set
                - Autogeneration count is not positive
                - Duration count is not positive
                - Unit of time is not set

        Examples:
            >>> # This will raise a ValidationError
            >>> type_invalid = self.env['date.range.type'].create({
            ...     'name': 'Invalid Type',
            ...     'autogeneration_count': 5,  # Count set but no start date
            ... })
            ValidationError: Autogeneration start date is required when autogeneration count is set for type 'Invalid Type'

            >>> # This is valid
            >>> type_valid = self.env['date.range.type'].create({
            ...     'name': 'Valid Type',
            ...     'autogeneration_count': 5,
            ...     'autogeneration_date_start': '2024-01-01',
            ...     'duration_count': 1,
            ...     'unit_of_time': str(MONTHLY),
            ... })
        """
        for record in self:
            if record.autogeneration_count:
                if not record.autogeneration_date_start:
                    raise ValidationError(
                        self.env._(
                            "Autogeneration start date is required when "
                            "autogeneration count is set for type '%s'"
                        )
                        % record.name
                    )
                if record.autogeneration_count < 1:
                    raise ValidationError(
                        self.env._(
                            "Autogeneration count must be positive for type '%s'"
                        )
                        % record.name
                    )
                if not record.duration_count or record.duration_count < 1:
                    raise ValidationError(
                        self.env._(
                            "Duration count must be positive when "
                            "autogeneration is enabled for type '%s'"
                        )
                        % record.name
                    )
                if not record.unit_of_time:
                    raise ValidationError(
                        self.env._(
                            "Unit of time must be set when "
                            "autogeneration is enabled for type '%s'"
                        )
                        % record.name
                    )

    @api.constrains("company_id")
    def _check_company_id(self):
        """Validate company consistency between type and its date ranges.

        This constraint ensures that if a date range type is assigned to a company,
        all its date ranges must belong to the same company.

        Raises:
            ValidationError: If trying to change the company of a type that has
                           date ranges assigned to a different company.

        Note:
            Can be bypassed by setting 'bypass_company_validation' in context.

        Examples:
            >>> # Create a type with ranges
            >>> type_with_ranges = self.env['date.range.type'].create({
            ...     'name': 'Type with Ranges',
            ...     'company_id': self.env.company.id,
            ... })
            >>> range = self.env['date.range'].create({
            ...     'name': 'Range 1',
            ...     'type_id': type_with_ranges.id,
            ...     'company_id': self.env.company.id,
            ...     'date_start': '2024-01-01',
            ...     'date_end': '2024-12-31',
            ... })
            >>> # This will raise a ValidationError
            >>> other_company = self.env['res.company'].create({'name': 'Other Company'})
            >>> type_with_ranges.company_id = other_company
            ValidationError: You cannot change the company, as this Date Range Type is assigned to Date Range 'Range 1'.
        """
        if not self.env.context.get("bypass_company_validation", False):
            for rec in self.sudo():
                if not rec.company_id:
                    continue
                if bool(
                    rec.date_range_ids.filtered(
                        lambda r, drt=rec: r.company_id
                        and r.company_id != drt.company_id
                    )
                ):
                    raise ValidationError(
                        self.env._(
                            "You cannot change the company, as this "
                            "Date Range Type is assigned to Date Range '%s'."
                        )
                        % (rec.date_range_ids.display_name)
                    )

    @api.depends("name_expr", "name_prefix")
    def _compute_range_name_preview(self):
        """Compute a preview of the range name that would be generated.

        This method generates a sample name using the current year as an example,
        helping users understand how their naming configuration will work.

        The preview uses either the name expression or prefix, applying it to
        a sample date range (current year).

        Examples:
            >>> # Using prefix
            >>> dr_type = self.env['date.range.type'].create({
            ...     'name': 'Monthly',
            ...     'name_prefix': 'M',
            ... })
            >>> dr_type.range_name_preview
            'M01'

            >>> # Using expression
            >>> dr_type.name_expr = "'FY%s' % date_start.strftime('%Y')"
            >>> dr_type.range_name_preview
            'FY2024'
        """
        year_start = fields.Datetime.now().replace(day=1, month=1)
        next_year = year_start + relativedelta(years=1)
        for dr_type in self:
            if dr_type.name_expr or dr_type.name_prefix:
                names = self.env["date.range.generator"]._generate_names(
                    [year_start, next_year], dr_type.name_expr, dr_type.name_prefix
                )
                dr_type.range_name_preview = names[0]
            else:
                dr_type.range_name_preview = False

    @api.depends("date_range_ids")
    def _compute_date_ranges_exist(self):
        """Compute whether any date ranges exist for this type.

        This computed field is used to quickly check if a type has any ranges
        without having to query the full list of ranges.

        Examples:
            >>> empty_type = self.env['date.range.type'].create({'name': 'Empty Type'})
            >>> empty_type.date_ranges_exist
            False
            >>> self.env['date.range'].create({
            ...     'name': 'Range',
            ...     'type_id': empty_type.id,
            ...     'date_start': '2024-01-01',
            ...     'date_end': '2024-12-31',
            ... })
            >>> empty_type.date_ranges_exist
            True
        """
        for dr_type in self:
            dr_type.date_ranges_exist = bool(dr_type.date_range_ids)

    @api.onchange("name_expr")
    def onchange_name_expr(self):
        """Clear the name prefix when a name expression is entered.

        This onchange ensures that only one naming method is used at a time.
        When a user enters a name expression, the simpler name prefix is cleared
        to avoid confusion.

        The reverse is not implemented because we don't want to wipe the
        users' painstakingly crafted expressions by accident.

        Note:
            This is a one-way operation. Clearing the expression won't restore
            the prefix.

        Examples:
            >>> dr_type = self.env['date.range.type'].new({
            ...     'name': 'Test Type',
            ...     'name_prefix': 'PREFIX',
            ... })
            >>> dr_type.name_expr = "'FY%s' % date_start.year"
            >>> dr_type.name_prefix
            False
        """
        if self.name_expr and self.name_prefix:
            self.name_prefix = False

    @api.model
    def autogenerate_ranges(self):
        """Automatically generate date ranges for types with autogeneration settings.

        This method is typically called by a scheduled action to automatically create
        date ranges for types that have autogeneration configured. It processes all
        types with complete autogeneration settings and creates ranges up to the
        specified future date.

        The method handles errors gracefully, logging warnings for individual failures
        without stopping the entire process.

        Returns:
            None: This method doesn't return a value but creates date ranges as side effects.

        Note:
            - Uses savepoints to ensure partial failures don't affect other types
            - Logs warnings for any types that fail to generate
            - Only processes types with all required autogeneration fields set

        Examples:
            >>> # Set up a type for autogeneration
            >>> auto_type = self.env['date.range.type'].create({
            ...     'name': 'Auto Quarter',
            ...     'duration_count': 3,
            ...     'unit_of_time': str(MONTHLY),
            ...     'autogeneration_count': 4,
            ...     'autogeneration_unit': str(YEARLY),
            ...     'autogeneration_date_start': '2024-01-01',
            ...     'name_prefix': 'Q',
            ... })
            >>> # Run autogeneration
            >>> self.env['date.range.type'].autogenerate_ranges()
            >>> # Check created ranges
            >>> auto_type.date_range_ids.mapped('name')
            ['Q01', 'Q02', 'Q03', 'Q04', ...]
        """
        logger = logging.getLogger(__name__)
        for dr_type in self.search(
            [
                ("autogeneration_count", "!=", False),
                ("autogeneration_unit", "!=", False),
                ("duration_count", "!=", False),
                ("unit_of_time", "!=", False),
            ]
        ):
            try:
                wizard = self.env["date.range.generator"].new({"type_id": dr_type.id})
                if not wizard.date_end:
                    # Nothing to generate
                    continue
                with self.env.cr.savepoint():
                    wizard.action_apply(batch=True)
            except Exception as e:
                logger.warning(
                    f"Error autogenerating ranges for date range type "
                    f"{dr_type.name}: {e}"
                )
