from .common import L10nMxEdiPayslipTransactionCase


class TestRayaListReport(L10nMxEdiPayslipTransactionCase):
    def setUp(self):
        super().setUp()
        self.raya_list_report = self.env["report.l10n_mx_edi_payslip.raya_list_report"]
        self.payslip_run_record = self.payslip_run_obj.create(
            {
                "name": "Test Payslip Run",
                "date_start": "2024-01-01",
                "date_end": "2024-01-31",
            }
        )
        self.payslip_record = self.create_payroll(date_from="2024-01-01", date_to="2024-01-31")
        self.payslip_record.payslip_run_id = self.payslip_run_record.id

    def test_001_department_defined(self):
        """Ensure that when the department is defined directly in the payslip record,
        the report includes this department in the batch values."""
        self.payslip_record.write({"department_id": self.employee.department_id.id})
        report_values = self.raya_list_report._get_report_values(docids=[self.payslip_run_record.id])
        batches = report_values.get("batches")
        self.assertIn(self.payslip_run_record, batches)
        self.assertIn(self.employee.department_id.name, batches[self.payslip_run_record])
        self.assertTrue(batches[self.payslip_run_record][self.employee.department_id.name])

    def test_002_without_department(self):
        """Ensure that when the department is not defined in the payslip,
        the report includes the department "Without Department" in the batch values."""
        self.payslip_record.write({"department_id": False})
        report_values = self.raya_list_report._get_report_values(docids=[self.payslip_run_record.id])
        batches = report_values.get("batches")
        self.assertIn(self.payslip_run_record, batches)
        self.assertIn("Without Department", batches[self.payslip_run_record])
        self.assertTrue(batches[self.payslip_run_record]["Without Department"])
