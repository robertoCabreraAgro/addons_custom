from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestUsers(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.date_range = cls.env["res.partner.age.range"]

    def test_01_age_range_constraints(self):
        with self.assertRaises(ValidationError):
            self.date_range.create({"age_from": 100, "age_to": 100, "name": "range1"})
        dr1 = self.date_range.create({"age_from": 100, "age_to": 105, "name": "range1"})
        self.assertEqual(dr1.age_from, 100)
        with self.assertRaises(ValidationError):
            self.date_range.create({"age_to": 105, "name": "range2"})
        dr2 = self.date_range.create({"age_to": 108, "name": "range2"})
        self.assertEqual(dr2.age_from, 106)
        with self.assertRaises(ValidationError):
            self.date_range.create({"age_from": 107, "age_to": 109, "name": "range3"})
        self.date_range.create({"age_from": 110, "age_to": 115, "name": "range3"})
        with self.assertRaises(ValidationError):
            self.date_range.create({"age_from": 109, "age_to": 113, "name": "range4"})
