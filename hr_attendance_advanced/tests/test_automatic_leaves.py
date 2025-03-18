from datetime import timedelta

from pytz import timezone

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("automatic_leaves")
class TestAutomaticLeaves(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.calendar = cls.env.ref("resource.resource_calendar_std_38h")

        cls.employee = cls.env["hr.employee"].create(
            {
                "name": "Test Employee",
                "exempt_absence_for_delay": False,
                "resource_calendar_id": cls.calendar.id,
                "tz": "America/Mexico_City",
            }
        )

        cls.employee_exempt = cls.env["hr.employee"].create(
            {
                "name": "Exempt Employee",
                "exempt_absence_for_delay": True,
            }
        )

        cls.employee_delete_leave = cls.env["hr.employee"].create(
            {
                "name": "Delete leave Employee",
                "exempt_absence_for_delay": False,
                "resource_calendar_id": cls.calendar.id,
                "tz": "America/Mexico_City",
            }
        )

        cls.company = cls.env["res.company"].create(
            {"name": "Test Company", "tolerance_check_in": 15}
        )
        cls.employee_delete_leave.write(
            {
                "company_id": cls.company.id,
            }
        )

        cls.employee.write(
            {
                "company_id": cls.company.id,
            }
        )

    def test_01_generate_absence_for_delay(self):
        """Test that an absence is generated when an employee is late.

        Simulates a late check-in for a non-exempt employee, and ensures that:
        - An absence is generated.
        - The absence is marked as auto-generated.
        - The absence corresponds to the 'Unpaid Leave' holiday type.
        """
        now = fields.Datetime.now() - timedelta(days=1)
        base_time = now.replace(hour=8, minute=0, second=0, microsecond=0)
        employee_tz = timezone(self.employee.tz or "UTC")
        base_time_with_tz = employee_tz.localize(base_time)
        base_time_naive = base_time_with_tz.astimezone(timezone("UTC")).replace(
            tzinfo=None
        )
        self.env["hr.attendance"].create(
            {
                "employee_id": self.employee.id,
                "check_in": base_time_naive + timedelta(minutes=20),
                "check_out": base_time_naive + timedelta(hours=4),
            }
        )
        self.env["hr.leave"].generate_absences_for_missing_attendance()

        leave = self.env["hr.leave"].search([("employee_id", "=", self.employee.id)])
        self.assertEqual(len(leave), 1)
        self.assertTrue(leave.auto_generated)
        self.assertEqual(
            leave.holiday_status_id, self.env.ref("hr_holidays.holiday_status_unpaid")
        )

    def test_02_no_absence_for_exempt_employee(self):
        """Test that no absence is generated for an exempt employee.

        Simulates a late check-in for an exempt employee and ensures that:
        - No absences are generated.
        """
        now = fields.Datetime.now() - timedelta(days=1)
        base_time = now.replace(hour=8, minute=0, second=0, microsecond=0)

        employee_tz = timezone(self.employee.tz or "UTC")
        base_time_with_tz = employee_tz.localize(base_time)
        base_time_naive = base_time_with_tz.astimezone(timezone("UTC")).replace(
            tzinfo=None
        )

        self.env["hr.attendance"].create(
            {
                "employee_id": self.employee_exempt.id,
                "check_in": base_time_naive + timedelta(minutes=20),
                "check_out": base_time_naive + timedelta(hours=4),
            }
        )

        self.env["hr.leave"].generate_absences_for_missing_attendance()

        leave_exempt = self.env["hr.leave"].search(
            [("employee_id", "=", self.employee_exempt.id)]
        )
        self.assertFalse(leave_exempt)

    def test_03_no_absence_if_leave_request_exists(self):
        """Test that no absence is generated if a leave request already exists.

        Simulates a late check-in for an employee with an existing leave request
        and ensures that:
        - A ValidationError is raised when trying to generate an absence.
        """
        now = fields.Datetime.now() - timedelta(days=1)
        base_time = now.replace(hour=8, minute=0, second=0, microsecond=0)

        employee_tz = timezone(self.employee.tz or "UTC")
        base_time_with_tz = employee_tz.localize(base_time)
        base_time_naive = base_time_with_tz.astimezone(timezone("UTC")).replace(
            tzinfo=None
        )

        self.env["hr.attendance"].create(
            {
                "employee_id": self.employee.id,
                "check_in": base_time_naive + timedelta(minutes=20),
                "check_out": base_time_naive + timedelta(hours=4),
            }
        )

        self.env["hr.leave"].create(
            {
                "name": "Existing Leave",
                "employee_id": self.employee.id,
                "holiday_status_id": self.env.ref(
                    "hr_holidays.holiday_status_unpaid"
                ).id,
                "request_date_from": fields.Datetime.now() - timedelta(days=1),
                "request_date_to": fields.Datetime.now() - timedelta(days=1),
            }
        )

        with self.assertRaises(ValidationError):
            self.env["hr.leave"].generate_absences_for_missing_attendance()

    def test_04_restriction_on_deleting_auto_generated_absence(self):
        """Test that auto-generated absences cannot be deleted.

        Simulates a late check-in for an employee, generates an absence,
        and ensures that:
        - The absence is marked as auto-generated.
        - A ValidationError is raised when trying to delete the absence.
        """
        now = fields.Datetime.now() - timedelta(days=1)
        base_time = now.replace(hour=8, minute=0, second=0, microsecond=0)

        employee_tz = timezone(self.employee.tz or "UTC")
        base_time_with_tz = employee_tz.localize(base_time)
        base_time_naive = base_time_with_tz.astimezone(timezone("UTC")).replace(
            tzinfo=None
        )

        self.env["hr.attendance"].create(
            {
                "employee_id": self.employee_delete_leave.id,
                "check_in": base_time_naive + timedelta(minutes=20),
                "check_out": base_time_naive + timedelta(hours=4),
            }
        )

        self.env["hr.leave"].generate_absences_for_missing_attendance()

        leave = self.env["hr.leave"].search(
            [("employee_id", "=", self.employee_delete_leave.id)]
        )
        self.assertTrue(leave.auto_generated)
        with self.assertRaises(ValidationError):
            leave.unlink()
