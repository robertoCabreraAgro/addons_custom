# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime

from freezegun import freeze_time

from odoo.tests import Form, tagged
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

from odoo.addons.stock_account.tests.test_anglo_saxon_valuation_reconciliation_common import (
    ValuationReconciliationTestCommon,
)


@freeze_time("2021-01-14 09:12:15")
@tagged("post_install", "-at_install")
class TestPurchase(ValuationReconciliationTestCommon):
    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        cls.product_id_1 = cls.env["product.product"].create({"name": "Large Desk", "purchase_method": "purchase"})
        cls.product_id_2 = cls.env["product.product"].create(
            {"name": "Conference Chair", "purchase_method": "purchase"}
        )

        cls.purchase_order_vals = {
            "partner_id": cls.partner_a.id,
            "order_line": [
                (
                    0,
                    0,
                    {
                        "name": cls.product_id_1.name,
                        "product_id": cls.product_id_1.id,
                        "product_qty": 5.0,
                        "product_uom": cls.product_id_1.uom_po_id.id,
                        "price_unit": 500.0,
                        "date_planned": datetime.today().replace(hour=9).strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                    },
                ),
                (
                    0,
                    0,
                    {
                        "name": cls.product_id_2.name,
                        "product_id": cls.product_id_2.id,
                        "product_qty": 5.0,
                        "product_uom": cls.product_id_2.uom_po_id.id,
                        "price_unit": 250.0,
                        "date_planned": datetime.today().replace(hour=9).strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                    },
                ),
            ],
        }

    def test_01_purchase_order_computed_values(self):
        purchase_order = self.env["purchase.order"].create(self.purchase_order_vals)
        self.assertTrue(purchase_order, "Purchase: no purchase order created")
        self.assertEqual(purchase_order.invoice_status, "no")

        # receipt_status
        purchase_order._compute_receipt_status()
        self.assertEqual(purchase_order.receipt_status, "no")
        purchase_order.action_force_reception_status()
        self.assertEqual(purchase_order.receipt_status, "full")
        purchase_order.action_unforce_reception_status()
        self.assertEqual(purchase_order.receipt_status, "no")
        self.assertTrue(purchase_order.order_line[0].product_updatable)
        purchase_order.button_confirm()
        self.assertEqual(purchase_order.receipt_status, "pending")

        self.assertEqual(purchase_order.invoice_status, "to invoice")

        line = purchase_order.order_line[0]
        self.assertEqual(line.qty_received_method, "stock_moves")
        self.assertEqual(line.qty_to_receive, 5.0)
        line.qty_received_method = False
        self.assertEqual(line.qty_to_receive, 0.0)
        line.qty_received_method = "stock_moves"
        self.assertEqual(line.qty_to_receive, 5.0)

        self.assertEqual(purchase_order.incoming_picking_count, 1, 'Purchase: one picking should be created"')
        self.picking = purchase_order.picking_ids[0]
        self.picking.move_line_ids.write({"quantity": 5.0})
        self.picking.move_ids.picked = True
        self.picking.button_validate()
        self.assertEqual(purchase_order.receipt_status, "full")
        self.assertEqual(purchase_order.order_line.mapped("qty_received"), [5.0, 5.0])
        self.assertEqual(line.qty_to_receive, 0.0)
        self.assertFalse(purchase_order.order_line[0].product_updatable)

        move_form = Form(self.env["account.move"].with_context(default_move_type="in_invoice"))
        move_form.partner_id = self.partner_a
        move_form.purchase_vendor_bill_id = self.env["purchase.bill.union"].browse(-purchase_order.id)
        self.invoice = move_form.save()
        self.assertEqual(purchase_order.order_line.mapped("qty_invoiced"), [5.0, 5.0])
        self.assertEqual(purchase_order.invoice_status, "invoiced")

    def test_02_view_purchase_from_picking(self):
        purchase_order = self.env["purchase.order"].create(self.purchase_order_vals)
        purchase_order.button_confirm()
        picking = purchase_order.picking_ids[0]
        res = picking.with_context(default_picking_id=picking.id).action_view_purchase_order()
        self.assertEqual(res.get("res_model"), "purchase.order")
        self.assertEqual(res.get("res_id"), purchase_order.id)
        self.assertFalse(res.get("context", {}).get("default_picking_id"))

    def test_03_purchase_order_line_change_partner(self):
        purchase_order = self.env["purchase.order"].create(self.purchase_order_vals)
        purchase_line = purchase_order.order_line[0]
        self.assertTrue(purchase_line.order_id)
        action = purchase_line.action_purchase_order_form()
        self.assertEqual(action["res_id"], purchase_line.order_id.id)
        self.assertEqual(action["res_model"], "purchase.order")
        self.assertEqual(action["views"], [(self.env.ref("purchase.purchase_order_form").id, "form")])

    def test_04_purchase_order_price_history(self):
        order = self.env["purchase.order"].create(self.purchase_order_vals)
        order2 = order.copy()
        order3 = order.copy()
        order.button_confirm()
        order2.order_line[0].price_unit = 750
        order2.button_confirm()
        order3.order_line[0].price_unit = 1000
        with Form(self.env["purchase.order.line.price.history"]) as form_wiz:
            form_wiz.product_id = order.order_line[0].product_id
            form_wiz.partner_id = order.partner_id
        wiz = form_wiz.save()
        wiz._onchange_partner_id()
        self.assertRecordValues(
            wiz.line_ids,
            [
                {
                    "line_id": order2.order_line[0].id,
                    "price_unit": 750,
                },
                {
                    "line_id": order.order_line[0].id,
                    "price_unit": 500,
                },
            ],
        )
        with Form(wiz) as form_wiz:
            form_wiz.include_rfq = True
        wiz = form_wiz.save()
        wiz._onchange_partner_id()
        self.assertRecordValues(
            wiz.line_ids,
            [
                {
                    "line_id": order3.order_line[0].id,
                    "price_unit": 1000,
                },
                {
                    "line_id": order2.order_line[0].id,
                    "price_unit": 750,
                },
                {
                    "line_id": order.order_line[0].id,
                    "price_unit": 500,
                },
            ],
        )

    def test_05_purchase_order_create_and_show(self):
        with Form(self.env["purchase.order.line"], view="marin.view_purchase_order_line_tree") as line_form:
            line_form.partner_id = self.partner_a
            line_form.product_id = self.product_id_1
            line_form.price_unit = 190.50
            line_form.product_uom = self.env.ref("uom.product_uom_unit")
            line_form.product_uom_qty = 8.0
            line_form.name = "Test line description"
        line = line_form.save()
        line._onchange_force_company_id()
        self.assertTrue(line.order_id)
        action_dict = line.action_purchase_order_form()
        self.assertEqual(action_dict["res_id"], line.order_id.id)
        self.assertEqual(action_dict["res_model"], "purchase.order")
