from datetime import datetime, timedelta

from pytz import timezone

from odoo.tests import tagged

from .common import L10nMxEdiPayslipTransactionCase


@tagged("attendance")
class TestHrAttendance(L10nMxEdiPayslipTransactionCase):
    def test_time_delay(self):
        self.env["hr.attendance"].unlink()
        monday = datetime.strptime("2021-07-16 08:00:00", "%Y-%m-%d %H:%M:%S")
        monday = monday.astimezone(timezone(self.employee.tz)).replace(hour=8).astimezone(timezone("UTC"))
        attendance = self.env["hr.attendance"].create(
            {
                "check_in": monday.strftime("%Y-%m-%d %H:%M:%S"),
                "employee_id": self.employee.id,
            }
        )
        self.assertFalse(attendance.l10n_mx_edi_time_delay, "Attendance in time delay.")
        attendance.check_in += timedelta(minutes=6)
        self.assertTrue(attendance.l10n_mx_edi_time_delay, "Attendance not in time delay.")
