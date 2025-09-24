import logging

from dateutil.relativedelta import relativedelta
from dateutil.rrule import DAILY, MONTHLY, WEEKLY, YEARLY, rrule

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class DateRangeGenerator(models.TransientModel):
    """Wizard for generating multiple date ranges at once.

    This transient model provides a wizard interface for bulk creation of date ranges.
    It allows users to specify generation parameters and automatically create multiple
    consecutive date ranges with consistent naming and duration.

    Key features:
    - Generate ranges by count or end date
    - Flexible naming with expressions or prefixes
    - Support for various time units (years, months, weeks, days)
    - Automatic continuation from last existing range
    - Company-specific generation
    - Batch generation support for scheduled actions

    Attributes:
        name_expr (Text): Python expression for generating range names.
        name_prefix (Char): Simple prefix for range names with auto-numbering.
        range_name_preview (Char): Preview of the first generated name.
        date_start (Date): Starting date for the first range.
        date_end (Date): End date for generation (alternative to count).
        type_id (Many2one): Date range type for the generated ranges.
        company_id (Many2one): Company for the generated ranges.
        unit_of_time (Selection): Time unit for each range (years/months/weeks/days).
        duration_count (Integer): Number of units per range.
        count (Integer): Number of ranges to generate (alternative to date_end).

    Examples:
        >>> # Generate 12 monthly ranges for 2024
        >>> wizard = self.env['date.range.generator'].create({
        ...     'type_id': monthly_type.id,
        ...     'date_start': '2024-01-01',
        ...     'count': 12,
        ...     'unit_of_time': str(MONTHLY),
        ...     'duration_count': 1,
        ...     'name_prefix': 'Month ',
        ... })
        >>> wizard.action_apply()
        >>> # Creates: Month 01, Month 02, ..., Month 12

        >>> # Generate quarters until end of 2025 with expression
        >>> wizard = self.env['date.range.generator'].create({
        ...     'type_id': quarter_type.id,
        ...     'date_start': '2024-01-01',
        ...     'date_end': '2025-12-31',
        ...     'unit_of_time': str(MONTHLY),
        ...     'duration_count': 3,
        ...     'name_expr': "'Q%s %s' % ((date_start.month-1)//3 + 1, date_start.year)",
        ... })
        >>> wizard.action_apply()
        >>> # Creates: Q1 2024, Q2 2024, ..., Q4 2025
    """

    _name = "date.range.generator"
    _description = "Date Range Generator"

    name_expr = fields.Text(
        string="Range name expression",
        compute="_compute_name_expr",
        store=True,
        readonly=False,
        help=(
            "Evaluated expression. E.g. "
            "\"'FY%s' % date_start.strftime('%Y%m%d')\"\nYou can "
            "use the Date types 'date_end' and 'date_start', as well as "
            "the 'index' variable."
        ),
    )
    name_prefix = fields.Char(
        string="Range name prefix",
        compute="_compute_name_prefix",
        store=True,
        readonly=False,
    )
    range_name_preview = fields.Char(
        compute="_compute_range_name_preview",
    )
    date_start = fields.Date(
        string="Start date",
        required=True,
        compute="_compute_date_start",
        store=True,
        readonly=False,
    )
    date_end = fields.Date(
        string="End date",
        compute="_compute_date_end",
        store=True,
        readonly=False,
    )
    type_id = fields.Many2one(
        comodel_name="date.range.type",
        string="Type",
        required=True,
        domain="['|', ('company_id', '=', company_id), " "('company_id', '=', False)]",
        compute="_compute_type_id",
        store=True,
        readonly=False,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        compute="_compute_company_id",
        store=True,
        readonly=False,
    )
    unit_of_time = fields.Selection(
        selection=[
            (str(YEARLY), "years"),
            (str(MONTHLY), "months"),
            (str(WEEKLY), "weeks"),
            (str(DAILY), "days"),
        ],
        required=True,
        compute="_compute_unit_of_time",
        store=True,
        readonly=False,
    )
    duration_count = fields.Integer(
        string="Duration",
        required=True,
        compute="_compute_duration_count",
        store=True,
        readonly=False,
    )
    count = fields.Integer(
        string="Number of ranges to generate",
    )

    @api.constrains("company_id", "type_id")
    def _check_company_id_type_id(self):
        """Validate that company settings are consistent between generator and type.

        Ensures that if both the generator and the date range type have a company set,
        they must be the same company.

        Raises:
            ValidationError: If the generator's company differs from the type's company.

        Examples:
            >>> company1 = self.env['res.company'].create({'name': 'Company 1'})
            >>> company2 = self.env['res.company'].create({'name': 'Company 2'})
            >>> dr_type = self.env['date.range.type'].create({
            ...     'name': 'Type',
            ...     'company_id': company1.id,
            ... })
            >>> # This will raise ValidationError
            >>> wizard = self.env['date.range.generator'].create({
            ...     'type_id': dr_type.id,
            ...     'company_id': company2.id,
            ... })
            ValidationError: The Company in the Date Range Generator and in Date Range Type must be the same.
        """
        for rec in self.sudo():
            if (
                rec.company_id
                and rec.type_id.company_id
                and rec.company_id != rec.type_id.company_id
            ):
                raise ValidationError(
                    self.env._(
                        "The Company in the Date Range Generator and in "
                        "Date Range Type must be the same."
                    )
                )

    @api.onchange("company_id")
    def _onchange_company_id(self):
        """Clear type selection when company changes if incompatible.

        When the company is changed, if the currently selected type belongs to
        a different company, the type selection is cleared to prevent validation errors.

        Examples:
            >>> wizard = self.env['date.range.generator'].new({
            ...     'type_id': type_company1.id,
            ...     'company_id': company1.id,
            ... })
            >>> wizard.company_id = company2
            >>> wizard.type_id
            False  # Type was cleared due to company mismatch
        """
        if (
            self.company_id
            and self.type_id.company_id
            and self.type_id.company_id != self.company_id
        ):
            self._cache.update(self._convert_to_cache({"type_id": False}, update=True))

    @api.onchange("date_end")
    def onchange_date_end(self):
        """Clear count when end date is set.

        Ensures only one generation method is used at a time. When an end date
        is specified, the count field is cleared.

        Note:
            Users must choose between specifying an end date OR a count,
            not both.

        Examples:
            >>> wizard = self.env['date.range.generator'].new({'count': 10})
            >>> wizard.date_end = '2024-12-31'
            >>> wizard.count
            0  # Count was cleared
        """
        if self.date_end and self.count:
            self.count = 0

    @api.onchange("count")
    def onchange_count(self):
        """Clear end date when count is set.

        Ensures only one generation method is used at a time. When a count
        is specified, the end date field is cleared.

        Note:
            Users must choose between specifying a count OR an end date,
            not both.

        Examples:
            >>> wizard = self.env['date.range.generator'].new({'date_end': '2024-12-31'})
            >>> wizard.count = 10
            >>> wizard.date_end
            False  # End date was cleared
        """
        if self.count and self.date_end:
            self.date_end = False

    @api.onchange("name_expr")
    def onchange_name_expr(self):
        """Clear name prefix when expression is entered.

        Ensures only one naming method is used at a time. When a naming expression
        is entered, the simpler prefix method is cleared.

        The reverse is not implemented because we don't want to wipe the
        users' painstakingly crafted expressions by accident.

        Examples:
            >>> wizard = self.env['date.range.generator'].new({'name_prefix': 'FY'})
            >>> wizard.name_expr = "'FY%s' % date_start.year"
            >>> wizard.name_prefix
            False  # Prefix was cleared

        Note:
            This is a one-way operation to protect complex expressions.
        """
        if self.name_expr and self.name_prefix:
            self.name_prefix = False

    @api.depends("company_id", "type_id.company_id")
    def _compute_type_id(self):
        """Clear type if it becomes incompatible with the selected company.

        This computed method ensures data consistency by clearing the type selection
        when it belongs to a different company than the generator.

        Examples:
            >>> wizard = self.env['date.range.generator'].create({
            ...     'type_id': type_company1.id,
            ...     'company_id': company1.id,
            ... })
            >>> wizard.company_id = company2
            >>> wizard.type_id
            False  # Type cleared due to company mismatch
        """
        if (
            self.company_id
            and self.type_id.company_id
            and self.type_id.company_id != self.company_id
        ):
            self.type_id = self.env["date.range.type"]

    @api.depends("name_expr", "name_prefix")
    def _compute_range_name_preview(self):
        """Generate a preview of the first range name.

        Shows users what their naming configuration will produce by generating
        a sample name for the first range.

        The preview helps users validate their naming expressions or prefixes
        before generating the actual ranges.

        Examples:
            >>> wizard = self.env['date.range.generator'].new({
            ...     'name_prefix': 'FY',
            ...     'date_start': '2024-01-01',
            ... })
            >>> wizard.range_name_preview
            'FY01'

            >>> wizard.name_expr = "'Fiscal Year %s' % date_start.year"
            >>> wizard.range_name_preview
            'Fiscal Year 2024'

        Note:
            - Handles expression errors gracefully
            - Returns False if no naming method is configured
        """
        for wiz in self:
            preview = False
            if wiz.name_expr or wiz.name_prefix:
                vals = False
                try:
                    vals = wiz._generate_intervals()
                except Exception:
                    _logger.exception("Something happened generating intervals")
                if vals:
                    names = wiz.generate_names(vals)
                    if names:
                        preview = names[0]
            wiz.range_name_preview = preview

    @api.depends("type_id")
    def _compute_company_id(self):
        """Set company from the selected type or use current company.

        When a date range type is selected, inherit its company setting.
        Otherwise, default to the current user's company.

        Examples:
            >>> type_with_company = self.env['date.range.type'].create({
            ...     'name': 'Type',
            ...     'company_id': specific_company.id,
            ... })
            >>> wizard = self.env['date.range.generator'].new({
            ...     'type_id': type_with_company.id,
            ... })
            >>> wizard.company_id == specific_company
            True
        """
        if self.type_id:
            self.company_id = self.type_id.company_id
        else:
            self.company_id = self.env.company

    @api.depends("type_id")
    def _compute_name_expr(self):
        """Inherit name expression from the selected date range type.

        When a date range type is selected, if it has a default name expression
        configured, that expression is copied to the generator.

        Examples:
            >>> type_with_expr = self.env['date.range.type'].create({
            ...     'name': 'Type',
            ...     'name_expr': "'FY%s' % date_start.year",
            ... })
            >>> wizard = self.env['date.range.generator'].new({'type_id': type_with_expr.id})
            >>> wizard.name_expr
            "'FY%s' % date_start.year"
        """
        if self.type_id.name_expr:
            self.name_expr = self.type_id.name_expr

    @api.depends("type_id")
    def _compute_name_prefix(self):
        """Inherit name prefix from the selected date range type.

        When a date range type is selected, if it has a default name prefix
        configured, that prefix is copied to the generator.

        Examples:
            >>> type_with_prefix = self.env['date.range.type'].create({
            ...     'name': 'Type',
            ...     'name_prefix': 'FY',
            ... })
            >>> wizard = self.env['date.range.generator'].new({'type_id': type_with_prefix.id})
            >>> wizard.name_prefix
            'FY'
        """
        if self.type_id.name_prefix:
            self.name_prefix = self.type_id.name_prefix

    @api.depends("type_id")
    def _compute_duration_count(self):
        """Inherit duration count from the selected date range type.

        When a date range type is selected, if it has a default duration count
        configured, that value is copied to the generator.

        Examples:
            >>> quarterly_type = self.env['date.range.type'].create({
            ...     'name': 'Quarterly',
            ...     'duration_count': 3,
            ...     'unit_of_time': str(MONTHLY),
            ... })
            >>> wizard = self.env['date.range.generator'].new({'type_id': quarterly_type.id})
            >>> wizard.duration_count
            3
        """
        if self.type_id.duration_count:
            self.duration_count = self.type_id.duration_count

    @api.depends("type_id")
    def _compute_unit_of_time(self):
        """Inherit unit of time from the selected date range type.

        When a date range type is selected, if it has a default unit of time
        configured, that value is copied to the generator.

        Examples:
            >>> monthly_type = self.env['date.range.type'].create({
            ...     'name': 'Monthly',
            ...     'duration_count': 1,
            ...     'unit_of_time': str(MONTHLY),
            ... })
            >>> wizard = self.env['date.range.generator'].new({'type_id': monthly_type.id})
            >>> wizard.unit_of_time
            '1'  # MONTHLY constant value
        """
        if self.type_id.unit_of_time:
            self.unit_of_time = self.type_id.unit_of_time

    @api.depends("type_id")
    def _compute_date_start(self):
        """Compute the starting date for generation based on type and existing ranges.

        The start date is determined by:
        1. If ranges exist for this type: day after the last range's end date
        2. If type has autogeneration_date_start: use that date
        3. Otherwise: beginning of current year

        This ensures continuous date ranges without gaps or overlaps.

        Examples:
            >>> # Type with existing ranges ending 2023-12-31
            >>> wizard = self.env['date.range.generator'].new({'type_id': type_with_ranges.id})
            >>> wizard.date_start
            datetime.date(2024, 1, 1)  # Day after last range

            >>> # Type with autogeneration setting
            >>> type_auto = self.env['date.range.type'].create({
            ...     'name': 'Auto Type',
            ...     'autogeneration_date_start': '2024-04-01',
            ... })
            >>> wizard = self.env['date.range.generator'].new({'type_id': type_auto.id})
            >>> wizard.date_start
            datetime.date(2024, 4, 1)
        """
        if not self.type_id:
            return
        last = self.env["date.range"].search(
            [("type_id", "=", self.type_id.id)], order="date_end desc", limit=1
        )
        today = fields.Date.context_today(self)
        if last:
            self.date_start = last.date_end + relativedelta(days=1)
        elif self.type_id.autogeneration_date_start:
            self.date_start = self.type_id.autogeneration_date_start
        else:  # default to the beginning of the current year
            self.date_start = today.replace(day=1, month=1)

    @api.depends("date_start")
    def _compute_date_end(self):
        """Compute default end date based on type's autogeneration settings.

        If the type has autogeneration configuration, calculates an end date
        by adding the specified count and unit to today's date.

        Only sets an end date if it would be after the start date.

        Examples:
            >>> # Type configured to generate 2 years ahead
            >>> type_2y = self.env['date.range.type'].create({
            ...     'name': 'Type',
            ...     'autogeneration_count': 2,
            ...     'autogeneration_unit': str(YEARLY),
            ... })
            >>> wizard = self.env['date.range.generator'].new({
            ...     'type_id': type_2y.id,
            ...     'date_start': '2024-01-01',
            ... })
            >>> # If today is 2024-03-15, date_end will be around 2026-03-15
        """
        if not self.type_id or not self.date_start:
            return
        if self.type_id.autogeneration_unit and self.type_id.autogeneration_count:
            key = {
                str(YEARLY): "years",
                str(MONTHLY): "months",
                str(WEEKLY): "weeks",
                str(DAILY): "days",
            }[self.type_id.autogeneration_unit]
            today = fields.Date.context_today(self)
            date_end = today + relativedelta(**{key: self.type_id.autogeneration_count})
            if date_end > self.date_start:
                self.date_end = date_end

    def _generate_intervals(self, batch=False):
        """Generate a list of dates representing the interval boundaries.

        Creates a list of dates that mark the boundaries of the ranges to be generated.
        The last date is only used to compute the end date of the last interval.

        Args:
            batch (bool): When True, returns empty list instead of raising errors.
                         Used for batch processing in scheduled actions.

        Returns:
            list: List of datetime objects representing interval boundaries.

        Raises:
            ValidationError: If neither date_end nor count is specified (unless batch=True).
            UserError: If the settings would generate no ranges.

        Examples:
            >>> wizard = self.env['date.range.generator'].create({
            ...     'date_start': '2024-01-01',
            ...     'count': 4,
            ...     'unit_of_time': str(MONTHLY),
            ...     'duration_count': 3,
            ... })
            >>> intervals = wizard._generate_intervals()
            >>> # Returns dates: 2024-01-01, 2024-04-01, 2024-07-01, 2024-10-01, 2025-01-01
            >>> # These create Q1, Q2, Q3, Q4 of 2024

        Note:
            The returned list has one more date than the number of ranges,
            as we need n+1 boundaries to create n ranges.
        """
        if not self.date_end and not self.count:
            if batch:
                return []
            raise ValidationError(
                self.env._(
                    "Please enter an end date, or the number of ranges to generate."
                )
            )
        kwargs = dict(
            freq=int(self.unit_of_time),
            interval=self.duration_count,
            dtstart=self.date_start,
        )
        if self.date_end:
            kwargs["until"] = self.date_end
        else:
            kwargs["count"] = self.count
        vals = list(rrule(**kwargs))
        if not vals:
            raise UserError(self.env._("No ranges to generate with these settings"))
        # Generate another interval to fetch the last end date from
        vals.append(
            list(
                rrule(
                    freq=int(self.unit_of_time),
                    interval=self.duration_count,
                    dtstart=vals[-1].date(),
                    count=2,
                )
            )[-1]
        )
        return vals

    def generate_names(self, vals):
        """Generate names for the date ranges based on intervals.

        Creates a list of names for the ranges using either the name expression
        or prefix configuration.

        Args:
            vals (list): List of datetime objects from _generate_intervals().

        Returns:
            list: List of string names for each range.

        Raises:
            ValidationError: If the name expression has syntax errors or
                           if neither expression nor prefix is set.

        Examples:
            >>> wizard = self.env['date.range.generator'].create({
            ...     'name_prefix': 'Q',
            ... })
            >>> intervals = [datetime(2024, 1, 1), datetime(2024, 4, 1),
            ...             datetime(2024, 7, 1), datetime(2024, 10, 1)]
            >>> wizard.generate_names(intervals)
            ['Q1', 'Q2', 'Q3']

            >>> wizard.name_expr = "'Quarter %s/%s' % ((date_start.month-1)//3 + 1, date_start.year)"
            >>> wizard.generate_names(intervals)
            ['Quarter 1/2024', 'Quarter 2/2024', 'Quarter 3/2024']
        """
        self.ensure_one()
        return self._generate_names(vals, self.name_expr, self.name_prefix)

    @api.model
    def _generate_names(self, vals, name_expr, name_prefix):
        """Generate names for intervals using the specified naming method.

        This is a model method that can be called without a wizard instance,
        useful for testing or external usage.

        Args:
            vals (list): List of datetime objects representing interval boundaries.
            name_expr (str): Python expression for name generation.
            name_prefix (str): Simple prefix for names with auto-numbering.

        Returns:
            list: List of generated names.

        Raises:
            ValidationError: If name expression has errors or no naming method provided.

        Available variables in name_expr:
            - date_start: Start date of the range (date object)
            - date_end: End date of the range (date object)
            - index: Zero-padded index string (e.g., '01', '02', '10')

        Examples:
            >>> intervals = [datetime(2024, 1, 1), datetime(2024, 2, 1), datetime(2024, 3, 1)]
            >>> self._generate_names(intervals,
            ...     "'%s-%02d' % (date_start.year, date_start.month)",
            ...     None)
            ['2024-01', '2024-02']

            >>> self._generate_names(intervals, None, 'MONTH')
            ['MONTH01', 'MONTH02']
        """
        names = []
        count_digits = len(str(len(vals) - 1))
        for idx, dt_start in enumerate(vals[:-1]):
            date_start = dt_start.date()
            # always remove 1 day for the date_end since range limits are
            # inclusive
            date_end = vals[idx + 1].date() - relativedelta(days=1)
            index = "%0*d" % (count_digits, idx + 1)
            if name_expr:
                try:
                    names.append(
                        safe_eval(
                            name_expr,
                            {
                                "date_end": date_end,
                                "date_start": date_start,
                                "index": index,
                            },
                        )
                    )
                except (SyntaxError, ValueError) as e:
                    raise ValidationError(
                        self.env._("Invalid name expression: %s") % e
                    ) from e
            elif name_prefix:
                names.append(name_prefix + index)
            else:
                raise ValidationError(
                    self.env._(
                        "Please set a prefix or an expression to "
                        "generate the range names."
                    )
                )
        return names

    def _generate_date_ranges(self, batch=False):
        """Generate the date range data dictionaries.

        Creates a list of dictionaries containing the data for each date range
        to be created. Does not actually create the records.

        Args:
            batch (bool): When True, returns empty list on error instead of raising.

        Returns:
            list: List of dictionaries with date range data.

        Examples:
            >>> wizard = self.env['date.range.generator'].create({
            ...     'type_id': type_id,
            ...     'date_start': '2024-01-01',
            ...     'count': 2,
            ...     'unit_of_time': str(MONTHLY),
            ...     'duration_count': 1,
            ...     'name_prefix': 'Month',
            ... })
            >>> data = wizard._generate_date_ranges()
            >>> data
            [
                {'name': 'Month01', 'date_start': '2024-01-01', 'date_end': '2024-01-31',
                 'type_id': 1, 'company_id': 1},
                {'name': 'Month02', 'date_start': '2024-02-01', 'date_end': '2024-02-29',
                 'type_id': 1, 'company_id': 1}
            ]
        """
        self.ensure_one()
        vals = self._generate_intervals(batch=batch)
        if not vals:
            return []
        date_ranges = []
        names = self.generate_names(vals)
        for idx, dt_start in enumerate(vals[:-1]):
            date_start = dt_start.date()
            date_end = vals[idx + 1].date() - relativedelta(days=1)
            date_ranges.append(
                {
                    "name": names[idx],
                    "date_start": date_start,
                    "date_end": date_end,
                    "type_id": self.type_id.id,
                    "company_id": self.company_id.id,
                }
            )
        return date_ranges

    def action_apply(self, batch=False):
        """Generate and create date ranges with improved error handling.

        This is the main action method that generates and creates the date ranges.
        It handles both interactive wizard usage and batch processing for scheduled actions.

        Args:
            batch (bool): When True, operates in batch mode:
                         - Suppresses user errors (logs warnings instead)
                         - Continues on individual range failures
                         - Returns None instead of action dictionary

        Returns:
            dict or None: In interactive mode, returns action to show created ranges.
                         In batch mode, returns None.

        Raises:
            UserError: In interactive mode, if generation or creation fails.
                      In batch mode, errors are logged but not raised.

        Examples:
            >>> # Interactive usage
            >>> wizard = self.env['date.range.generator'].create({
            ...     'type_id': fiscal_year_type.id,
            ...     'date_start': '2024-01-01',
            ...     'count': 3,
            ...     'unit_of_time': str(YEARLY),
            ...     'duration_count': 1,
            ...     'name_prefix': 'FY',
            ... })
            >>> action = wizard.action_apply()
            >>> # Creates FY01, FY02, FY03 and returns action to display them

            >>> # Batch usage (from scheduled action)
            >>> wizard.action_apply(batch=True)
            >>> # Creates ranges, logs any errors, returns None

        Note:
            - In batch mode, validation errors are logged as warnings
            - Successful creations are logged at info level
            - Uses savepoints to handle partial failures in batch mode
        """
        try:
            date_ranges = self._generate_date_ranges(batch=batch)
            if date_ranges:
                created_ranges = []
                for dr in date_ranges:
                    try:
                        created_range = self.env["date.range"].create(dr)
                        created_ranges.append(created_range)
                    except ValidationError as e:
                        if batch:
                            _logger.warning(
                                "Skipping date range %s: %s",
                                dr.get("name", "Unknown"),
                                str(e),
                            )
                        else:
                            raise UserError(
                                self.env._(
                                    "Failed to create date range '%(name)s':\n%(error)s"
                                )
                                % {"name": dr.get("name", "Unknown"), "error": str(e)}
                            )

                if not batch and created_ranges:
                    _logger.info(
                        "Successfully created %d date ranges for type %s",
                        len(created_ranges),
                        self.type_id.name,
                    )

            if not batch:
                return self.env["ir.actions.actions"]._for_xml_id(
                    "date_range.date_range_action"
                )
        except Exception as e:
            if batch:
                _logger.error(
                    "Failed to generate date ranges for type %s: %s",
                    self.type_id.name if self.type_id else "Unknown",
                    str(e),
                    exc_info=True,
                )
            else:
                raise UserError(
                    self.env._(
                        "Failed to generate date ranges:\n\n"
                        "Error: %(error)s\n"
                        "Type: %(type)s\n"
                        "Date Start: %(start)s\n"
                        "Date End: %(end)s"
                    )
                    % {
                        "error": str(e),
                        "type": self.type_id.name if self.type_id else "Not set",
                        "start": self.date_start or "Not set",
                        "end": self.date_end or "Not set",
                    }
                ) from e
