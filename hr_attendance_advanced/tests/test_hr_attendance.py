from datetime import datetime

from odoo.tests import Form, TransactionCase, new_test_user, tagged


@tagged("pre_work_time_hours")
class TestHrAttendance(TransactionCase):
    """Testing the attendance with the following cases:
    Case 1: The check is false, counting after hours and not counting pre work hours
    Case 2: The check is false, not counting after hours and counting pre work hours
    Case 3: The check is false, counting after hours and counting pre work hours
    Case 4: The check is true, counting after hours and not counting pre work hours
    Case 5: The check is true, not counting after hours and counting pre work hours
    Case 6: The check is true, counting after hours and counting pre work hours
    """

    def test_01_employee_attendance(self):
        company = self.env["res.company"].create(
            {
                "name": "SweatChipChop Inc.",
                "attendance_overtime_validation": "by_manager",
                "overtime_company_threshold": 10,
                "overtime_employee_threshold": 10,
            }
        )
        user = new_test_user(
            self.env,
            login="fru",
            groups="base.group_user,hr_attendance.group_hr_attendance_manager",
            company_id=company.id,
        ).with_company(company)
        employee = self.env["hr.employee"].create(
            {
                "name": "Marie-Edouard De La Court",
                "user_id": user.id,
                "company_id": company.id,
                "tz": "UTC",
            }
        )

        # Case 1: The check is false, counting after hours and not counting pre work hours

        attendance_form = Form(self.env["hr.attendance"])
        attendance_form.employee_id = employee
        attendance_form.check_in = datetime(2024, 1, 4, 8, 0)
        attendance_form.check_out = datetime(2024, 1, 4, 19, 0)
        attendance = attendance_form.save()
        self.assertEqual(attendance.overtime_hours, 2)

        # Case 2: The check is false, not counting after hours and counting pre work hours

        with Form(attendance) as attendance_form:
            attendance_form.check_in = datetime(2024, 1, 4, 6, 0)
            attendance_form.check_out = datetime(2024, 1, 4, 17, 0)
        attendance = attendance_form.save()
        self.assertEqual(attendance.overtime_hours, 2)

        # Case 3: The check is false, counting after hours and counting pre work hours

        with Form(attendance) as attendance_form:
            attendance_form.check_in = datetime(2024, 1, 4, 6, 0)
            attendance_form.check_out = datetime(2024, 1, 4, 19, 0)
        attendance = attendance_form.save()
        self.assertEqual(round(attendance.overtime_hours), 4)

        # Case 4: The check is true, counting after hours and not counting pre work hours
        company.exclude_previous_work_time = True

        with Form(attendance) as attendance_form:
            attendance_form.check_in = datetime(2024, 1, 4, 8, 0)
            attendance_form.check_out = datetime(2024, 1, 4, 19, 0)
        attendance = attendance_form.save()
        self.assertEqual(round(attendance.overtime_hours), 2)

        # Case 5: The check is true, not counting after hours and counting pre work hours

        with Form(attendance) as attendance_form:
            attendance_form.check_in = datetime(2024, 1, 4, 6, 0)
            attendance_form.check_out = datetime(2024, 1, 4, 17, 0)
        attendance = attendance_form.save()
        self.assertEqual(round(attendance.overtime_hours), 0)

        # Case 6: The check is true, counting after hours and counting pre work hours

        with Form(attendance) as attendance_form:
            attendance_form.check_in = datetime(2024, 1, 4, 6, 0)
            attendance_form.check_out = datetime(2024, 1, 4, 19, 0)
        attendance = attendance_form.save()
        self.assertEqual(round(attendance.overtime_hours), 2)
