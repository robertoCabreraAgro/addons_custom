from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestCompany(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_01_compute_complete_name(self):
        company = self.env["res.company"].create(
            {
                "name": "Test Company",
                "code": "TEST",
            }
        )
        self.assertEqual(company.complete_name, "TEST - Test Company")
        company.code = False
        self.assertEqual(company.complete_name, "Test Company")
        company2 = self.env["res.company"].name_search("Test")
        self.assertEqual(company.id, company2[0][0])
