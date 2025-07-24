import logging
from datetime import datetime, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    lunch_out = fields.Datetime(help="Time the employee clocked out for lunch.")
    lunch_in = fields.Datetime(help="Time the employee clocked back in from lunch.")
    lunch_hours = fields.Float(compute="_compute_lunch_hours", store=True, readonly=True)

    @api.depends("lunch_in", "lunch_out")
    def _compute_lunch_hours(self):
        """Calculates the duration of the lunch break in hours."""
        for attendance in self:
            if attendance.lunch_in and attendance.lunch_out:
                delta = attendance.lunch_in - attendance.lunch_out
                attendance.lunch_hours = delta.total_seconds() / 3600.0
            else:
                attendance.lunch_hours = 0.0

    @api.constrains("lunch_in", "lunch_out")
    def _check_lunch_times(self):
        """Adds constraints to ensure the logic of lunch times is valid.
        - Lunch out must be before lunch in.
        - Lunch times must be between check-in and check-out.
        """
        for attendance in self:
            if attendance.lunch_out:
                if not attendance.check_in or attendance.lunch_out < attendance.check_in:
                    raise ValidationError(_('"Lunch Out" time cannot be earlier than "Check In" time.'))
                if attendance.check_out and attendance.lunch_out > attendance.check_out:
                    raise ValidationError(_('"Lunch Out" time cannot be later than "Check Out" time.'))

            if attendance.lunch_in:
                if not attendance.lunch_out:
                    raise ValidationError(_('Cannot have a "Lunch In" time without a "Lunch Out" time.'))
                if attendance.lunch_in < attendance.lunch_out:
                    raise ValidationError(_('"Lunch In" time cannot be earlier than "Lunch Out" time.'))
                if attendance.check_out and attendance.lunch_in > attendance.check_out:
                    raise ValidationError(_('"Lunch In" time cannot be later than "Check Out" time.'))

    def _cron_auto_checkout_at_day_end(self):
        """This method is called by a cron job to automatically close attendances
        that were left open at the end of the previous day.
        """
        _logger.info("Starting cron job: Auto-checkout for attendances left open...")

        # Define the time window for the previous day in UTC.
        today_start_utc = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start_utc = today_start_utc - timedelta(days=1)

        # Get all attendances from yesterday that are still open.
        open_attendances = self.search(
            [
                ("check_in", ">=", yesterday_start_utc),
                ("check_in", "<", today_start_utc),
                ("check_out", "=", False),
            ]
        )

        for att in open_attendances:
            employee = att.employee_id
            if not employee.resource_calendar_id:
                _logger.warning(
                    "Skipping auto-checkout for attendance %s: Employee or calendar not found.",
                    att.id,
                )
                continue

            calendar = employee.resource_calendar_id
            tz = pytz.timezone(employee.tz or "UTC")

            check_in_local = pytz.utc.localize(att.check_in).astimezone(tz)
            weekday = str(check_in_local.weekday())

            # Find the scheduled working hours for that day of the week
            day_attendances = calendar.attendance_ids.filtered(lambda a: a.dayofweek == weekday)

            if not day_attendances:
                # Fallback: If the employee wasn't scheduled to work, ignore,
                # they will have to check out eventually
                continue
            # Find the latest scheduled checkout time for that day
            latest_hour_to = max(day_attendances.mapped("hour_to"))

            hour = int(latest_hour_to)
            minute = int((latest_hour_to * 60) % 60)

            # Create the checkout time in the employee's local timezone
            checkout_time_local = check_in_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
            checkout_time_utc = checkout_time_local.astimezone(pytz.utc).replace(tzinfo=None)

            # Sanity check: if the calculated checkout is before the check-in (e.g., they checked in after hours),
            # set the checkout to the end of their check-in day as a safe fallback.
            if checkout_time_utc < att.check_in:
                checkout_time_utc = (
                    check_in_local.replace(hour=23, minute=59, second=59).astimezone(pytz.utc).replace(tzinfo=None)
                )

            att.write({"check_out": checkout_time_utc})
            att.message_post(body=_("This attendance was automatically closed by the system at the end of the day."))
            _logger.info(
                "Automatically checked out attendance %s for employee %s.",
                att.id,
                employee.name,
            )
        _logger.info("Finished cron job: Auto-checkout.")
