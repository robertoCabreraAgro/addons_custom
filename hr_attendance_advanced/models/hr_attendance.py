import time
from datetime import timedelta

from pytz import timezone

from odoo import api, fields, models
from odoo.tools import format_duration


class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    is_time_delay = fields.Boolean(
        "Time Delay?",
        compute="_compute_is_time_delay",
        store=True,
        help="If the check-in is out of time and the difference is bigger than the tolerance time, "
        "it will mark the record and be considered in salary rules related.",
    )

    @api.depends("employee_id", "check_in")
    def _compute_is_time_delay(self):
        """Compute if the attendance check-in is a delay."""
        for record in self:
            if not record.check_in or not record.employee_id:
                record.is_time_delay = False
                continue

            tolerance = record.employee_id.company_id.tolerance_check_in
            check_in = record.check_in.astimezone(timezone(record.employee_id.tz))

            day_period = "morning" if not record._is_first_attendace() else "afternoon"
            resource = record.employee_id.resource_calendar_id.attendance_ids.filtered(
                lambda a: a.dayofweek == str(check_in.isocalendar()[2] - 1)
                and a.day_period == day_period
            )
            if len(resource) != 1:
                continue

            hour_from = time.strptime(format_duration(resource.hour_from), "%H:%M")
            check_in_day_start = check_in.replace(
                hour=hour_from.tm_hour, minute=hour_from.tm_min, second=0, microsecond=0
            )
            check_in_limit = check_in_day_start + timedelta(minutes=tolerance)
            record.is_time_delay = check_in > check_in_limit

    def _get_pre_post_work_time(self, employee, working_times, attendance_date):
        """The Odoo native method counts as overtime if an employee starts working before the start of
        the workday.

        If the company field exclude_previous_work_time is True this method sets the pre-work time as 0.
        """

        pre_work_time, work_duration, post_work_time, planned_work_duration = (
            super()._get_pre_post_work_time(employee, working_times, attendance_date)
        )
        if employee.company_id.exclude_previous_work_time:
            pre_work_time = 0
        return pre_work_time, work_duration, post_work_time, planned_work_duration

    def _is_first_attendace(self):
        self.ensure_one()
        return self.search(
            [
                ("id", "!=", self._origin.id),
                ("employee_id", "=", self.employee_id.id),
                ("check_in", ">=", self.check_in.replace(hour=0).replace(minute=0)),
                ("check_out", "<=", self.check_in.replace(hour=23).replace(minute=59)),
            ]
        )
