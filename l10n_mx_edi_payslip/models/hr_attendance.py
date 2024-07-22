import time
from datetime import timedelta

from pytz import timezone

from odoo import api, fields, models
from odoo.tools import format_duration


class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    l10n_mx_edi_time_delay = fields.Boolean(
        "Time Delay?",
        compute="_compute_l10n_mx_edi_time_delay",
        store=True,
        help="If the check in is out of time and the "
        "difference is bigger than the tolerance time will to mark the record and will be considered in the salary "
        "rules related.",
    )

    @api.depends("employee_id", "check_in")
    def _compute_l10n_mx_edi_time_delay(self):
        """Is True if the check in is > to calendar hour from + tolerance in the company."""
        for record in self:
            if not record.check_in or not record.employee_id:
                record.l10n_mx_edi_time_delay = False
                continue
            tolerance = record.employee_id.company_id.l10n_mx_edi_tolerance_check_in
            check_in = record.check_in.astimezone(timezone(record.employee_id.tz))
            day_period = "morning" if not record._is_first_attendace() else "afternoon"
            resource = record.employee_id.resource_calendar_id.attendance_ids.filtered(
                lambda a: a.dayofweek == str(check_in.isocalendar()[2] - 1) and a.day_period == day_period
            )
            if len(resource) != 1:
                continue
            hour_from = time.strptime(format_duration(resource.hour_from), "%H:%M")
            record.l10n_mx_edi_time_delay = check_in > check_in.replace(hour=hour_from.tm_hour).replace(
                minute=hour_from.tm_min
            ) + timedelta(minutes=tolerance)

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
