from odoo import Command
from odoo.tests import tagged

from odoo.addons.account.tests.test_account_analytic import TestAccountAnalyticAccount


@tagged("post_install", "-at_install")
class TestAnalyticLine(TestAccountAnalyticAccount):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_01_analytic_line_vehicle(self):
        """Ensure that analytic lines compute the field vehicle_id based on the move line and can be changed"""
        brand = self.env["fleet.vehicle.model.brand"].create(
            {
                "name": "Audi",
            }
        )
        vmodel = self.env["fleet.vehicle.model"].create(
            {
                "brand_id": brand.id,
                "name": "A3",
            }
        )
        car_1 = self.env["fleet.vehicle"].create(
            {"model_id": vmodel.id, "driver_id": self.env.user.partner_id.id, "plan_to_change_car": False}
        )

        car_2 = self.env["fleet.vehicle"].create(
            {"model_id": vmodel.id, "driver_id": self.env.user.partner_id.id, "plan_to_change_car": False}
        )
        out_invoice = self.env["account.move"].create(
            [
                {
                    "move_type": "out_invoice",
                    "partner_id": self.partner_a.id,
                    "date": "2017-01-01",
                    "invoice_date": "2017-01-01",
                    "invoice_line_ids": [
                        Command.create(
                            {
                                "product_id": self.product_a.id,
                                "price_unit": 200.0,
                                "analytic_distribution": {
                                    self.analytic_account_a.id: 100,
                                    self.analytic_account_b.id: 50,
                                },
                                "vehicle_id": car_1.id,
                            }
                        )
                    ],
                }
            ]
        )
        move_line = out_invoice.line_ids[0]
        out_invoice.action_post()
        analytic_line = (
            self.env["account.analytic.line"].search([("move_line_id", "in", move_line.ids)]).sorted("amount")[0]
        )
        self.assertEqual(move_line.vehicle_id, car_1)
        self.assertEqual(analytic_line.vehicle_id, move_line.vehicle_id)
        analytic_line.vehicle_id = car_2
        self.assertEqual(move_line.vehicle_id, car_1)
        self.assertEqual(analytic_line.vehicle_id, car_2)
        move_line.vehicle_id = False
        self.assertFalse(move_line.vehicle_id)
        self.assertEqual(analytic_line.vehicle_id, move_line.vehicle_id)
