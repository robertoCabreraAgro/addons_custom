import logging
from datetime import datetime, time, timedelta

from pytz import UTC, timezone

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HrLeave(models.Model):
    _inherit = "hr.leave"

    auto_generated = fields.Boolean(
        string="Automatically Generated",
        help="Indicates if the leave was generated automatically due to a delay.",
    )

    @api.ondelete(at_uninstall=False)
    def _unlink_if_auto_generated(self):
        if self.filtered("auto_generated"):
            raise ValidationError(
                self.env._(
                    "The absence is linked to an automatically generated attendance record. "
                    "If the absence is not valid, please reject it to prevent it from being considered in the payroll."
                )
            )

    @api.model
    def generate_absences_for_missing_attendance(self):
        today = fields.Date.context_today(self)
        yesterday = today - timedelta(days=1)

        attendances = self.env["hr.attendance"].search(
            [
                ("check_in", ">=", datetime.combine(yesterday, time.min)),
                ("check_in", "<=", datetime.combine(yesterday, time.max)),
                ("is_time_delay", "=", True),
                ("employee_id.exempt_absence_for_delay", "=", False),
            ]
        )
        leave_type = self.env.ref("hr_holidays.holiday_status_unpaid")

        for attendance in attendances:
            employee = attendance.employee_id
            user_tz = employee.tz or "UTC"
            local_tz = timezone(user_tz)

            check_in_local = UTC.localize(attendance.check_in).astimezone(local_tz)
            check_out_local = (
                UTC.localize(attendance.check_out).astimezone(local_tz)
                if attendance.check_out
                else None
            )

            absence_from = check_in_local.replace(tzinfo=None)
            absence_to = check_out_local.replace(tzinfo=None) or (
                check_in_local + timedelta(hours=8)
            ).replace(tzinfo=None)

            leave = self.env["hr.leave"].create(
                {
                    "name": self.env._("Absence generated due to delay."),
                    "employee_id": employee.id,
                    "holiday_status_id": leave_type.id,
                    "request_date_from": absence_from,
                    "request_date_to": absence_to,
                    "auto_generated": True,
                }
            )
            leave.message_post(
                body=self.env._(
                    "This leave request has been automatically generated due to a delay. "
                    "Please review it. If it is not valid, reject it to prevent it from "
                    "being included in payroll."
                ),
            )
