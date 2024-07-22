# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.hr_contract.tests.test_contract import TestHrContracts


@tagged("test_contracts")
class TestHRContracts(TestHrContracts):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_01_hr_contract_incoming_overlapping_contract(self):
        start = datetime.strptime("2015-11-01", "%Y-%m-%d").date()
        end = datetime.strptime("2015-11-30", "%Y-%m-%d").date()
        self.create_contract("open", "normal", start, end)
        # Incoming contract
        with self.assertRaises(ValidationError, msg="It should not create two contract in state open or incoming"):
            start = datetime.strptime("2015-11-15", "%Y-%m-%d").date()
            end = datetime.strptime("2015-12-30", "%Y-%m-%d").date()
            self.create_contract("draft", "done", start, end)

    def test_02_hr_contract_pending_overlapping_contract(self):
        start = datetime.strptime("2015-11-01", "%Y-%m-%d").date()
        end = datetime.strptime("2015-11-30", "%Y-%m-%d").date()
        self.create_contract("open", "normal", start, end)
        # Pending contract
        with self.assertRaises(ValidationError, msg="It should not create two contract in state open or pending"):
            start = datetime.strptime("2015-11-15", "%Y-%m-%d").date()
            end = datetime.strptime("2015-12-30", "%Y-%m-%d").date()
            self.create_contract("open", "blocked", start, end)
        # Draft contract -> should not raise
        start = datetime.strptime("2015-11-15", "%Y-%m-%d").date()
        end = datetime.strptime("2015-12-30", "%Y-%m-%d").date()
        self.create_contract("draft", "normal", start, end)

    def test_03_hr_contract_draft_overlapping_contract(self):
        start = datetime.strptime("2015-11-01", "%Y-%m-%d").date()
        end = datetime.strptime("2015-11-30", "%Y-%m-%d").date()
        self.create_contract("open", "normal", start, end)
        # Draft contract -> should not raise even if overlapping
        start = datetime.strptime("2015-11-15", "%Y-%m-%d").date()
        end = datetime.strptime("2015-12-30", "%Y-%m-%d").date()
        self.create_contract("draft", "normal", start, end)

    def test_04_hr_contract_overlapping_contract_no_end(self):
        # No end date
        self.create_contract("open", "normal", datetime.strptime("2015-11-01", "%Y-%m-%d").date())
        with self.assertRaises(ValidationError):
            start = datetime.strptime("2015-11-15", "%Y-%m-%d").date()
            end = datetime.strptime("2015-12-30", "%Y-%m-%d").date()
            self.create_contract("draft", "done", start, end)

    def test_05_hr_contract_overlapping_contract_no_end_2(self):
        start = datetime.strptime("2015-11-01", "%Y-%m-%d").date()
        end = datetime.strptime("2015-12-30", "%Y-%m-%d").date()
        self.create_contract("open", "normal", start, end)
        with self.assertRaises(ValidationError):
            # No end
            self.create_contract("draft", "done", datetime.strptime("2015-01-01", "%Y-%m-%d").date())

    def test_06_hr_contract_year_days(self):
        contract = self.env["hr.contract"]
        date1 = datetime.strptime("2015-01-01", "%Y-%m-%d").date()
        date2 = datetime.strptime("2024-02-02", "%Y-%m-%d").date()
        date3 = datetime.strptime("1900-03-03", "%Y-%m-%d").date()
        date4 = datetime.strptime("2000-04-04", "%Y-%m-%d").date()
        self.assertEqual(contract._l10n_mx_edi_year_days(date1), 365)
        self.assertEqual(contract._l10n_mx_edi_year_days(date2), 366)
        self.assertEqual(contract._l10n_mx_edi_year_days(date3), 365)
        self.assertEqual(contract._l10n_mx_edi_year_days(date4), 366)
