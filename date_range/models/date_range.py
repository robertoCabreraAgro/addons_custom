from datetime import timedelta
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DateRange(models.Model):
    """Date Range model for managing time periods.

    This model provides functionality to:
    - Define and manage date ranges with start and end dates
    - Calculate business days, working hours, and holidays
    - Support hierarchical structure with parent/child relationships
    - Integrate with resource calendars for working time calculations
    - Provide utility methods for date range operations

    Attributes:
        _name: Technical name of the model
        _description: Human-readable description
        _check_company_auto: Enable automatic company checks
        _order: Default ordering for records
    """

    _name = "date.range"
    _description = "Date Range"
    _check_company_auto = True
    _order = "type_id, date_start"

    name = fields.Char(required=True, translate=True)
    date_start = fields.Date(string="Start date", required=True, index=True)
    date_end = fields.Date(string="End date", required=True, index=True)
    type_id = fields.Many2one(
        comodel_name="date.range.type",
        string="Type",
        index=True,
        required=True,
        ondelete="restrict",
        check_company=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        index=True,
        default=lambda self: self.env.company.id,
    )
    active = fields.Boolean(
        help="The active field allows you to hide the date range without "
        "removing it.",
        compute="_compute_active",
        readonly=False,
        store=True,
    )
    duration_days = fields.Integer(
        string="Duration (days)",
        compute="_compute_duration",
        store=True,
        help="Number of days in this date range (inclusive)",
    )
    business_days = fields.Integer(
        string="Business Days",
        compute="_compute_business_days",
        store=True,
        help="Number of business days (Mon-Fri) in this date range",
    )
    weekend_days = fields.Integer(
        string="Weekend Days",
        compute="_compute_business_days",
        store=True,
        help="Number of weekend days (Sat-Sun) in this date range",
    )
    # Optional: link to holidays that affect business days calculation
    exclude_public_holidays = fields.Boolean(
        string="Exclude Public Holidays",
        default=False,
        help="If checked, public holidays will be excluded from business days count",
    )
    holiday_count = fields.Integer(
        string="Holidays",
        compute="_compute_business_days",
        store=True,
        help="Number of public holidays in this date range (if exclude_public_holidays is checked)",
    )
    # Resource calendar for advanced working time calculations
    resource_calendar_id = fields.Many2one(
        "resource.calendar",
        string="Working Schedule",
        help="Define custom working hours and days for this date range. "
        "If set, business days calculation will use this calendar instead of standard Mon-Fri.",
    )
    working_hours = fields.Float(
        string="Working Hours",
        compute="_compute_working_hours",
        store=True,
        help="Total working hours in this date range based on the selected calendar",
    )
    daily_working_hours = fields.Float(
        string="Avg Daily Hours",
        compute="_compute_working_hours",
        store=True,
        help="Average working hours per business day",
    )
    # Parent/child relationship for sub-ranges
    parent_id = fields.Many2one(
        "date.range",
        string="Parent Range",
        index=True,
        ondelete="cascade",
        check_company=True,
    )
    child_ids = fields.One2many("date.range", "parent_id", string="Sub-ranges")
    is_sub_range = fields.Boolean(
        string="Is Sub-range", compute="_compute_is_sub_range", store=True
    )

    def init(self):
        """Initialize database indexes for optimized range queries.

        Creates a GiST (Generalized Search Tree) index on the date range
        using PostgreSQL's built-in daterange type. This significantly
        improves performance for overlap detection and range queries.

        The index is partial, only covering active records to reduce
        index size and maintenance overhead.

        Note:
            This method is called when the module is installed or updated.
            Requires PostgreSQL with GiST support.
        """
        self.env.cr.execute(
            """
            CREATE INDEX IF NOT EXISTS date_range_daterange_idx
            ON date_range USING GIST (daterange(date_start, date_end, '[]'))
            WHERE active = true;
        """
        )

    _date_range_uniq = models.Constraint(
        "UNIQUE(name, type_id, company_id)",
        "A date range must be unique per Company",
    )

    @api.constrains("type_id", "date_start", "date_end", "company_id", "parent_id")
    def _validate_range(self):
        """Validate date range constraints.

        Performs comprehensive validation including:
        - Date order validation (start must be before or equal to end)
        - Sub-range containment (must be within parent range)
        - Overlap detection (if not allowed by type)

        Raises:
            ValidationError: If any validation constraint is violated
                - When start date is after end date
                - When sub-range extends beyond parent range
                - When ranges overlap (if type doesn't allow overlaps)

        Note:
            Uses PostgreSQL's daterange type for efficient overlap detection.
        """
        for this in self:
            if this.date_start > this.date_end:
                raise ValidationError(
                    self.env._(
                        "%(name)s is not a valid range "
                        "(%(date_start)s > %(date_end)s)"
                    )
                    % {
                        "name": this.name,
                        "date_start": this.date_start,
                        "date_end": this.date_end,
                    }
                )
            # Validate sub-range dates are within parent range
            if this.parent_id:
                if this.date_start < this.parent_id.date_start:
                    raise ValidationError(
                        self.env._(
                            "Sub-range '%(name)s' start date (%(start)s) "
                            "cannot be before parent range start date (%(parent_start)s)"
                        )
                        % {
                            "name": this.name,
                            "start": this.date_start,
                            "parent_start": this.parent_id.date_start,
                        }
                    )
                if this.date_end > this.parent_id.date_end:
                    raise ValidationError(
                        self.env._(
                            "Sub-range '%(name)s' end date (%(end)s) "
                            "cannot be after parent range end date (%(parent_end)s)"
                        )
                        % {
                            "name": this.name,
                            "end": this.date_end,
                            "parent_end": this.parent_id.date_end,
                        }
                    )
            if this.type_id.allow_overlap:
                continue
            # here we use a plain SQL query to benefit of the daterange
            # function available in PostgresSQL
            # (http://www.postgresql.org/docs/current/static/rangetypes.html)
            SQL = """
                SELECT
                    id
                FROM
                    date_range dt
                WHERE
                    DATERANGE(dt.date_start, dt.date_end, '[]') &&
                        DATERANGE(%s::date, %s::date, '[]')
                    AND dt.id != %s
                    AND dt.active
                    AND dt.company_id = %s
                    AND dt.type_id=%s;"""
            self.env.cr.execute(
                SQL,
                (
                    this.date_start,
                    this.date_end,
                    this.id,
                    this.company_id.id or None,
                    this.type_id.id,
                ),
            )
            res = self.env.cr.fetchall()
            if res:
                dt = self.browse(res[0][0])
                raise ValidationError(
                    self.env._("%(thisname)s overlaps %(dtname)s")
                    % {"thisname": this.name, "dtname": dt.name}
                )

    @api.depends("type_id.active")
    def _compute_active(self):
        """Compute active state based on type's active state.

        A date range is automatically deactivated when its type is deactivated.
        This ensures consistency and prevents orphaned active ranges.

        Note:
            This is a computed stored field that updates automatically
            when the related type's active state changes.
        """
        for date in self:
            if date.type_id.active:
                date.active = True
            else:
                date.active = False

    @api.depends("date_start", "date_end")
    def _compute_duration(self):
        """Compute the total duration in days.

        Calculates the number of days between start and end dates (inclusive).
        For example, a range from Jan 1 to Jan 3 has a duration of 3 days.

        Sets:
            duration_days: Number of days in the range, or 0 if dates are missing
        """
        for record in self:
            if record.date_start and record.date_end:
                delta = record.date_end - record.date_start
                record.duration_days = delta.days + 1
            else:
                record.duration_days = 0

    @api.depends(
        "date_start",
        "date_end",
        "exclude_public_holidays",
        "company_id",
        "resource_calendar_id",
    )
    def _compute_business_days(self):
        """Compute business days, weekend days, and holidays.

        Calculates working days based on:
        - Resource calendar (if set): Uses calendar's working schedule
        - Standard calculation: Monday-Friday as business days
        - Holiday exclusion: Optionally excludes public holidays

        Sets:
            business_days: Number of working days
            weekend_days: Number of non-working days
            holiday_count: Number of public holidays (if enabled)

        Note:
            If resource_calendar_id is set, it takes precedence over
            the standard Mon-Fri calculation.
        """
        for record in self:
            if record.date_start and record.date_end:
                if record.resource_calendar_id:
                    # Use resource calendar for calculation
                    record._compute_business_days_with_calendar()
                else:
                    # Standard calculation (Mon-Fri)
                    business_days = 0
                    weekend_days = 0
                    holiday_days = 0

                    # Get public holidays if needed
                    public_holidays = set()
                    if record.exclude_public_holidays:
                        public_holidays = record._get_public_holidays()

                    # Iterate through each day in the range
                    current_date = record.date_start
                    while current_date <= record.date_end:
                        weekday = current_date.weekday()

                        # Check if it's a weekend (Saturday=5, Sunday=6)
                        if weekday in (5, 6):
                            weekend_days += 1
                        # Check if it's a public holiday (on a weekday)
                        elif current_date in public_holidays:
                            holiday_days += 1
                        # Otherwise it's a business day
                        else:
                            business_days += 1

                        current_date += timedelta(days=1)

                    record.business_days = business_days
                    record.weekend_days = weekend_days
                    record.holiday_count = holiday_days
            else:
                record.business_days = 0
                record.weekend_days = 0
                record.holiday_count = 0

    def _compute_business_days_with_calendar(self):
        """Compute business days using a specific resource calendar.

        Uses the assigned resource calendar to calculate:
        - Working days based on calendar attendance
        - Non-working days (total days minus working days)
        - Company-wide holidays from calendar leaves

        This method is called when resource_calendar_id is set,
        providing more accurate calculations for non-standard schedules.

        Note:
            Requires resource module to be installed.
        """
        self.ensure_one()
        calendar = self.resource_calendar_id

        # Get working days from calendar
        working_days = calendar.get_work_days_data(
            fields.Datetime.combine(self.date_start, fields.Datetime.min.time()),
            fields.Datetime.combine(self.date_end, fields.Datetime.max.time()),
        )

        self.business_days = working_days.get("days", 0)

        # Calculate weekend days (days not in working days)
        total_days = (self.date_end - self.date_start).days + 1
        self.weekend_days = total_days - self.business_days

        # Get holidays from calendar leaves
        if self.exclude_public_holidays:
            holidays = calendar.leaves_ids.filtered(
                lambda l: l.date_from.date() <= self.date_end
                and l.date_to.date() >= self.date_start
                and not l.resource_id  # Company-wide holidays
            )
            self.holiday_count = len(holidays)
        else:
            self.holiday_count = 0

    @api.depends("date_start", "date_end", "resource_calendar_id", "business_days")
    def _compute_working_hours(self):
        """Compute total working hours and average daily hours.

        Calculates:
        - Total working hours: Based on calendar or 8-hour standard days
        - Average daily hours: Working hours divided by business days

        Sets:
            working_hours: Total hours available for work
            daily_working_hours: Average hours per business day

        Note:
            Falls back to 8-hour days if no calendar is specified.
        """
        for record in self:
            if record.date_start and record.date_end and record.resource_calendar_id:
                # Calculate total working hours using the calendar
                start_dt = fields.Datetime.combine(
                    record.date_start, fields.Datetime.min.time()
                )
                end_dt = fields.Datetime.combine(
                    record.date_end, fields.Datetime.max.time()
                )

                # Get working hours from calendar
                working_hours = record.resource_calendar_id.get_work_hours_count(
                    start_dt, end_dt
                )

                record.working_hours = working_hours

                # Calculate average daily hours
                if record.business_days:
                    record.daily_working_hours = working_hours / record.business_days
                else:
                    record.daily_working_hours = 0
            else:
                # If no calendar, estimate based on standard 8-hour days
                if record.business_days:
                    record.working_hours = record.business_days * 8.0
                    record.daily_working_hours = 8.0
                else:
                    record.working_hours = 0
                    record.daily_working_hours = 0

    @api.depends("parent_id")
    def _compute_is_sub_range(self):
        """Determine if this date range is a sub-range.

        A sub-range is any date range that has a parent range.
        This is used for hierarchical organization (e.g., months within quarters).

        Sets:
            is_sub_range: True if has parent, False otherwise
        """
        for record in self:
            record.is_sub_range = bool(record.parent_id)

    def get_domain(self, field_name):
        """Generate a search domain for records within this date range.

        Creates an Odoo domain that filters records where the specified
        field falls within this date range.

        Args:
            field_name (str): Name of the date field to filter on

        Returns:
            list: Odoo domain expression [(field, '>=', start), (field, '<=', end)]

        Example:
            >>> range.get_domain('invoice_date')
            [('invoice_date', '>=', date(2024, 1, 1)),
             ('invoice_date', '<=', date(2024, 12, 31))]
        """
        self.ensure_one()
        return [(field_name, ">=", self.date_start), (field_name, "<=", self.date_end)]

    def _get_public_holidays(self):
        """Get public holidays within the date range.

        This method can be overridden to integrate with hr_holidays or
        other holiday management modules.

        :return: Set of date objects representing public holidays
        """
        self.ensure_one()
        holidays = set()

        # Try to use hr_holidays if available
        if "hr.holidays.public" in self.env:
            holiday_model = self.env["hr.holidays.public"]
            # Search for public holidays in the date range
            domain = [
                "|",
                ("date_from", "<=", self.date_end),
                ("date_to", ">=", self.date_start),
            ]
            if self.company_id:
                domain.append(("company_id", "in", [False, self.company_id.id]))

            public_holidays = holiday_model.search(domain)
            for holiday in public_holidays:
                # Add all dates in the holiday period
                current = max(holiday.date_from, self.date_start)
                end = min(holiday.date_to or holiday.date_from, self.date_end)
                while current <= end:
                    holidays.add(current)
                    current += timedelta(days=1)

        # Alternative: Try resource.calendar.leaves (standard Odoo)
        elif "resource.calendar.leaves" in self.env:
            leaves_model = self.env["resource.calendar.leaves"]
            domain = [
                ("date_from", "<=", self.date_end),
                ("date_to", ">=", self.date_start),
                ("resource_id", "=", False),  # Company-wide holidays
            ]
            if self.company_id:
                domain.append(("company_id", "=", self.company_id.id))

            leaves = leaves_model.search(domain)
            for leave in leaves:
                # Convert datetime to date and add to holidays
                current_date = (
                    leave.date_from.date() if leave.date_from else self.date_start
                )
                end_date = leave.date_to.date() if leave.date_to else self.date_end
                current_date = max(current_date, self.date_start)
                end_date = min(end_date, self.date_end)

                while current_date <= end_date:
                    # Only add if it's a weekday
                    if current_date.weekday() < 5:
                        holidays.add(current_date)
                    current_date += timedelta(days=1)

        return holidays

    def get_working_days_count(self):
        """Get the count of working days.

        Returns the number of business days in the range,
        which already accounts for weekends and optionally holidays.

        Returns:
            int: Number of working days

        Note:
            This is a convenience method that returns the
            pre-computed business_days field value.
        """
        self.ensure_one()
        return self.business_days

    def get_business_days_between(self, start_date, end_date):
        """Calculate business days between two dates within this range.

        Computes working days for a sub-period within the date range,
        useful for partial period calculations.

        Args:
            start_date (date): Start date for calculation
            end_date (date): End date for calculation

        Returns:
            int: Number of business days in the specified period

        Note:
            Dates are automatically clipped to the range boundaries.
            Returns 0 if the period doesn't overlap with the range.
        """
        self.ensure_one()
        # Ensure dates are within the range
        start = max(start_date, self.date_start)
        end = min(end_date, self.date_end)

        if start > end:
            return 0

        business_days = 0
        public_holidays = set()
        if self.exclude_public_holidays:
            public_holidays = self._get_public_holidays()

        current = start
        while current <= end:
            if current.weekday() < 5 and current not in public_holidays:
                business_days += 1
            current += timedelta(days=1)

        return business_days

    @api.model
    def get_current_range(self, type_name=None, date=None, company_id=None):
        """Find the date range containing a specific date.

        Searches for an active date range that contains the given date,
        with optional filtering by type and company.

        Args:
            type_name (str, optional): Filter by range type name
            date (date, optional): Date to check (defaults to today)
            company_id (int, optional): Filter by company ID

        Returns:
            date.range: First matching range or empty recordset

        Example:
            >>> DateRange.get_current_range('Fiscal Year', date(2024, 6, 15))
            date.range(42,)  # Returns FY 2024 range
        """
        if not date:
            date = fields.Date.today()

        domain = [
            ("date_start", "<=", date),
            ("date_end", ">=", date),
            ("active", "=", True),
        ]

        if type_name:
            domain.append(("type_id.name", "=", type_name))

        if company_id:
            domain.append(("company_id", "=", company_id))

        return self.search(domain, limit=1)

    def get_next_range(self):
        """Get the next consecutive date range of the same type.

        Finds the next range that starts after this range ends,
        useful for period navigation.

        Returns:
            date.range: Next range or empty recordset if none exists

        Example:
            >>> q1_2024.get_next_range()
            date.range(43,)  # Returns Q2 2024
        """
        self.ensure_one()
        return self.search(
            [
                ("type_id", "=", self.type_id.id),
                ("date_start", ">", self.date_end),
                ("company_id", "=", self.company_id.id),
                ("active", "=", True),
            ],
            order="date_start",
            limit=1,
        )

    def get_previous_range(self):
        """Get the previous consecutive date range of the same type.

        Finds the range that ends before this range starts,
        useful for period navigation.

        Returns:
            date.range: Previous range or empty recordset if none exists

        Example:
            >>> q2_2024.get_previous_range()
            date.range(41,)  # Returns Q1 2024
        """
        self.ensure_one()
        return self.search(
            [
                ("type_id", "=", self.type_id.id),
                ("date_end", "<", self.date_start),
                ("company_id", "=", self.company_id.id),
                ("active", "=", True),
            ],
            order="date_end desc",
            limit=1,
        )

    def get_capacity_hours(self, efficiency_rate=1.0):
        """Calculate available capacity hours with efficiency factor.

        Computes the effective working hours considering an efficiency rate,
        useful for realistic capacity planning.

        Args:
            efficiency_rate (float): Efficiency factor between 0.0 and 1.0
                - 1.0 = 100% efficiency (default)
                - 0.85 = 85% efficiency (common for planning)

        Returns:
            float: Adjusted working hours

        Example:
            >>> range.get_capacity_hours(0.85)  # 85% efficiency
            1360.0  # From 1600 total hours
        """
        self.ensure_one()
        return self.working_hours * efficiency_rate

    def get_utilization_rate(self, used_hours):
        """Calculate resource utilization rate as a percentage.

        Determines what percentage of available working hours
        have been used or allocated.

        Args:
            used_hours (float): Number of hours already consumed

        Returns:
            float: Utilization percentage (0-100), capped at 100

        Example:
            >>> range.working_hours
            160.0
            >>> range.get_utilization_rate(120)
            75.0  # 75% utilized
        """
        self.ensure_one()
        if self.working_hours:
            return min((used_hours / self.working_hours) * 100, 100)
        return 0

    def get_available_slots(self, slot_duration_hours, buffer_hours=0):
        """Calculate number of available time slots.

        Divides available working hours into fixed-duration slots,
        useful for appointment scheduling or batch planning.

        Args:
            slot_duration_hours (float): Duration of each slot in hours
            buffer_hours (float, optional): Buffer time between slots

        Returns:
            int: Number of complete slots that fit in the range

        Example:
            >>> range.working_hours
            160.0
            >>> range.get_available_slots(2, 0.5)  # 2hr slots, 30min buffer
            64  # Can fit 64 slots
        """
        self.ensure_one()
        if not self.working_hours or slot_duration_hours <= 0:
            return 0

        effective_slot_duration = slot_duration_hours + buffer_hours
        return int(self.working_hours / effective_slot_duration)

    def split_by_calendar_periods(self):
        """Split date range into sub-ranges based on calendar periods.

        Automatically creates weekly or monthly sub-ranges depending on
        the parent range duration. Useful for hierarchical period breakdown.

        Returns:
            list: Dictionary values for creating sub-ranges, each containing:
                - name: Generated sub-range name
                - date_start: Sub-range start date
                - date_end: Sub-range end date
                - type_id: Same as parent type
                - parent_id: Reference to this range
                - resource_calendar_id: Inherited from parent
                - company_id: Inherited from parent

        Note:
            - Ranges <= 31 days are split by week
            - Ranges > 31 days are split by month
            - Requires resource_calendar_id to be set

        Example:
            >>> q1_2024.split_by_calendar_periods()
            [{'name': 'Q1 2024 - January 2024', ...},
             {'name': 'Q1 2024 - February 2024', ...},
             {'name': 'Q1 2024 - March 2024', ...}]
        """
        self.ensure_one()
        if not self.resource_calendar_id:
            return []

        sub_ranges = []
        current_start = self.date_start

        # Get attendance intervals from calendar
        attendances = self.resource_calendar_id.attendance_ids.sorted("dayofweek")

        # Group by week or month based on range duration
        if self.duration_days <= 31:
            # Split by week
            while current_start <= self.date_end:
                week_end = current_start + timedelta(days=6)
                week_end = min(week_end, self.date_end)

                sub_ranges.append(
                    {
                        "name": f"{self.name} - Week {current_start.strftime('%V')}",
                        "date_start": current_start,
                        "date_end": week_end,
                        "type_id": self.type_id.id,
                        "parent_id": self.id,
                        "resource_calendar_id": self.resource_calendar_id.id,
                        "company_id": self.company_id.id,
                    }
                )

                current_start = week_end + timedelta(days=1)
        else:
            # Split by month
            while current_start <= self.date_end:
                # Get last day of current month
                if current_start.month == 12:
                    month_end = current_start.replace(day=31)
                else:
                    month_end = current_start.replace(
                        month=current_start.month + 1, day=1
                    ) - timedelta(days=1)
                month_end = min(month_end, self.date_end)

                sub_ranges.append(
                    {
                        "name": f"{self.name} - {current_start.strftime('%B %Y')}",
                        "date_start": current_start,
                        "date_end": month_end,
                        "type_id": self.type_id.id,
                        "parent_id": self.id,
                        "resource_calendar_id": self.resource_calendar_id.id,
                        "company_id": self.company_id.id,
                    }
                )

                current_start = month_end + timedelta(days=1)

        return sub_ranges
