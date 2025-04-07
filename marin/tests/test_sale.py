from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests.common import Form, tagged

from odoo.addons.sale.tests.common import TestSaleCommon


@tagged("post_install", "-at_install")
class TestSale(TestSaleCommon):
    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        cls.product = cls.env["product.product"].create(
            {
                "name": "Product A",
                "type": "product",
                "tracking": "lot",
                "categ_id": cls.env.ref("product.product_category_all").id,
            }
        )
        cls.sale_order = (
            cls.env["sale.order"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "partner_id": cls.partner_a.id,
                    "partner_invoice_id": cls.partner_a.id,
                    "partner_shipping_id": cls.partner_a.id,
                    "pricelist_id": cls.company_data["default_pricelist"].id,
                    "order_line_ids": [
                        Command.create(
                            {
                                "product_id": cls.company_data["product_order_no"].id,
                                "product_uom_qty": 5,
                                "tax_id": False,
                                "price_unit": 5.0,
                            }
                        ),
                    ],
                }
            )
        )
        cls.partner_x = cls.partner_a.copy()
        cls.stock_location = cls.env["stock.location"].create(
            {
                "name": "stock_location",
                "usage": "internal",
            }
        )
        cls.shelf3 = cls.env["stock.location"].create(
            {
                "name": "Shelf 3",
                "usage": "internal",
                "location_id": cls.stock_location.id,
            }
        )
        cls.subshelf31 = cls.env["stock.location"].create(
            {
                "name": "Sub shelf 3-1",
                "usage": "internal",
                "location_id": cls.shelf3.id,
            }
        )
        cls.default_journal_id = cls.company_data["default_journal_sale"].id
        cls.pay_term_net_30_days = cls.env["account.payment.term"].create(
            {
                "name": "Net 30 days",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "value_amount": 100,
                            "value": "percent",
                            "nb_days": 30,
                        },
                    ),
                ],
            }
        )
        cls.lot = cls.env["stock.lot"].create(
            {
                "product_id": cls.product.id,
                "name": "Lot 1",
                "company_id": cls.env.company.id,
            }
        )
        cls.quant = cls.env["stock.quant"].create(
            {
                "product_id": cls.product.id,
                "location_id": cls.subshelf31.id,
                "quantity": 100,
                "lot_id": cls.lot.id,
            }
        )
        # cls.company_test = cls.env["res.company"].create({"name": "Test company"})

    def test_01_sale_order_computed_values(self):
        # journal_id
        order = self.sale_order
        order.journal_id = False
        self.assertFalse(order.journal_id)
        order._compute_journal_id()
        self.assertEqual(order.journal_id.id, self.default_journal_id)
        self.assertTrue(order.order_line_ids.product_updatable)

        # partner_credit_warning
        order._compute_partner_credit_warning()

        # delivery_status
        order._compute_transfer_state()
        self.assertEqual(order.delivery_status, "no")
        order.action_force_delivery_status()
        self.assertEqual(order.delivery_status, "full")
        order.action_unforce_delivery_status()
        self.assertEqual(order.delivery_status, "no")
        order.action_confirm()
        self.assertEqual(order.delivery_status, "pending")
        self.assertFalse(order.order_line_ids.product_updatable)

    def test_02_sale_order_authorize_debt(self):
        order = self.sale_order
        order.payment_term_id = self.pay_term_net_30_days
        partner = order.commercial_partner_id
        order.company_id.account_use_credit_limit = True
        partner.credit_limit = 10
        order.order_line_ids.price_unit = 10.0
        order._compute_partner_credit_warning()
        partner.credit_on_hold = True
        self.env.user.group_ids = [
            (3, self.env.ref("marin.group_account_debt_manager").id)
        ]
        with self.assertRaisesRegex(
            UserError,
            "The partner's credit line has been held. Contact the Credit Manager.",
        ):
            order.action_confirm()
        partner.credit_on_hold = False
        with self.assertRaises(UserError):
            order.action_confirm()
        self.env.user.group_ids = [
            (4, self.env.ref("marin.group_account_debt_manager").id)
        ]
        res = order.action_confirm()
        self.assertEqual(order.state, "draft")
        self.assertEqual(res.get("res_model"), "authorize.debt.wizard")
        wizard = (
            self.env["authorize.debt.wizard"]
            .with_context(**res.get("context"))
            .create([{}])
        )
        wizard._compute_from_record_ids()
        self.assertEqual(wizard.flag, "credit")
        self.assertEqual(wizard.count_so, 1)
        self.assertEqual(wizard.count_move, 0)
        wizard.action_so_increase_credit_limit_and_confirm()
        self.assertEqual(order.state, "sale")
        self.assertEqual(partner.credit_limit, 50)

    def test_03_view_sale_from_picking(self):
        order = self.sale_order
        order2 = self.sale_order.copy()
        order.action_confirm()
        order2.action_confirm()
        picking = order.picking_ids[0]
        picking2 = order2.picking_ids[0]
        res = picking.with_context(
            default_picking_id=picking2.id
        ).action_view_sale_order()
        self.assertEqual(res.get("res_model"), "sale.order")
        self.assertEqual(res.get("res_id"), order.id)
        self.assertFalse(res.get("context", {}).get("default_picking_id"))
        picking._get_movable_quants()
        picking2.action_cancel()
        self.assertEqual(picking2.state, "cancel")
        picking2.action_draft()
        self.assertEqual(picking2.state, "draft")
        picking2.location_id = self.shelf3
        with self.assertRaisesRegex(UserError, "Please choose a source end location"):
            picking2._validate_picking()
        picking2.location_id = self.subshelf31
        with self.assertRaisesRegex(UserError, "Moves lines already exists"):
            picking2._validate_picking()

    def test_04_sale_order_authorize_debt_multi(self):
        self.env.user.group_ids = [
            (4, self.env.ref("marin.group_account_debt_manager").id)
        ]
        order = self.sale_order
        order.payment_term_id = self.pay_term_net_30_days
        partner = order.commercial_partner_id
        order.company_id.account_use_credit_limit = True
        partner.credit_limit = 10
        order.order_line_ids.price_unit = 10.0
        order._compute_partner_credit_warning()
        order2 = order.copy()
        res = order.action_confirm()
        self.assertEqual(order.state, "draft")
        self.assertEqual(res.get("res_model"), "authorize.debt.wizard")
        res["context"]["active_ids"] = (order | order2).ids
        wizard = (
            self.env["authorize.debt.wizard"]
            .with_context(**res["context"])
            .create([{}])
        )
        wizard._compute_from_record_ids()
        self.assertEqual(wizard.flag, "credit")
        self.assertEqual(wizard.count_so, 2)
        self.assertEqual(wizard.count_move, 0)
        wizard.action_so_increase_credit_limit_and_confirm()
        self.assertEqual(order.state, "sale")
        self.assertEqual(order2.state, "sale")
        self.assertEqual(partner.credit_limit, 100)

    def test_05_sale_order_authorize_errors(self):
        self.env.user.group_ids = [
            (4, self.env.ref("marin.group_account_debt_manager").id)
        ]
        ctx = {"active_model": "sale.order", "active_ids": []}
        with self.assertRaisesRegex(
            UserError,
            "You can't authorize debt because the records dont match the criteria.",
        ):
            self.env["authorize.debt.wizard"].with_context(**ctx).create([{}])
        order = self.sale_order
        order2 = order.copy({"partner_id": self.partner_x.id})
        ctx["active_ids"] = (order | order2).ids
        with self.assertRaisesRegex(
            UserError,
            "You cant authorize debt for records belonging to different partners.",
        ):
            self.env["authorize.debt.wizard"].with_context(**ctx).create([{}])
        # order3 = order.copy({"company_id": self.company_test.id})
        # ctx["active_ids"] = (order | order3).ids
        # with self.assertRaisesRegex(
        #     UserError, "You cant authorize debt for records belonging to different companies."):
        #     self.env["authorize.debt.wizard"].with_context(**ctx).create([{}])
        order.order_line_ids.price_unit = 0.0
        ctx["active_ids"] = order.ids
        with self.assertRaisesRegex(
            UserError,
            "You can't authorize debt because the records dont match the criteria.",
        ):
            self.env["authorize.debt.wizard"].with_context(**ctx).create([{}])
        order.order_line_ids.price_unit = 10.0
        order.action_confirm()
        with self.assertRaisesRegex(
            UserError, "You can only authorize debt for quotations."
        ):
            self.env["authorize.debt.wizard"].with_context(**ctx).create([{}])
        ctx = {"active_model": "purchase.order", "active_ids": []}
        wizard = self.env["authorize.debt.wizard"].with_context(**ctx).create([{}])
        self.assertTrue(wizard)
        wizard._compute_from_record_ids()
        self.assertFalse(wizard.flag)
        self.assertFalse(wizard.partner_id)
        self.assertFalse(wizard.debt_request)
        self.assertFalse(wizard.amount_authorize)

    def test_06_sale_order_line_ids_order_view(self):
        sale_line = self.sale_order.order_line_ids
        action = sale_line.action_sale_order_form()
        self.assertEqual(action["res_id"], sale_line.order_id.id)
        self.assertEqual(action["res_model"], "sale.order")
        self.assertEqual(
            action["views"], [(self.env.ref("sale.view_order_form").id, "form")]
        )

    def test_07_picking_type_search(self):
        order = self.sale_order
        order.action_confirm()
        picking = order.picking_ids[0]
        with self.assertRaisesRegex(UserError, "Operation not supported"):
            ready_picking_types = picking.picking_type_id.search(
                [("count_picking_ready", ">", 0)]
            )
        ready_picking_types = picking.picking_type_id.search(
            [("count_picking_ready", "=", True)]
        )
        with self.assertRaisesRegex(UserError, "Operation not supported"):
            waiting_picking_types = picking.picking_type_id.search(
                [("count_picking_waiting", ">", 0)]
            )
        waiting_picking_types = picking.picking_type_id.search(
            [("count_picking_waiting", "!=", False)]
        )
        self.assertEqual(picking.picking_type_id, ready_picking_types)
        self.assertEqual(len(waiting_picking_types), 0)
        action = picking.picking_type_id.action_move_location()
        self.assertFalse(action.get("context", {}).get("default_edit_locations"))

    def test_08_sale_order_price_history(self):
        order = self.sale_order
        order2 = self.sale_order.copy()
        order3 = self.sale_order.copy()
        order.action_confirm()
        order2.order_line_ids.price_unit = 7.50
        order2.action_confirm()
        order3.order_line_ids.price_unit = 10.00
        with Form(self.env["sale.order.line.price.history"]) as form_wiz:
            form_wiz.product_id = order.order_line_ids.product_id
            form_wiz.partner_id = order.partner_id
        wiz = form_wiz.save()
        wiz._onchange_partner_id()
        self.assertRecordValues(
            wiz.line_ids,
            [
                {
                    "line_id": order2.order_line_ids.id,
                    "price_unit": 7.5,
                },
                {
                    "line_id": order.order_line_ids.id,
                    "price_unit": 5.0,
                },
            ],
        )
        with Form(wiz) as form_wiz:
            form_wiz.include_quotations = True
        wiz = form_wiz.save()
        wiz._onchange_partner_id()
        self.assertRecordValues(
            wiz.line_ids,
            [
                {
                    "line_id": order3.order_line_ids.id,
                    "price_unit": 10.0,
                },
                {
                    "line_id": order2.order_line_ids.id,
                    "price_unit": 7.5,
                },
                {
                    "line_id": order.order_line_ids.id,
                    "price_unit": 5.0,
                },
            ],
        )

    def test_09_sale_order_create_and_show(self):
        with Form(
            self.env["sale.order.line"], view="marin.view_order_line_tree_marin"
        ) as line_form:
            line_form.partner_id = self.partner_a
            line_form.product_id = self.product
            line_form.price_unit = 190.50
            line_form.product_uom = self.env.ref("uom.product_uom_unit")
            line_form.product_uom_qty = 8.0
            line_form.name = "Test line description"
        line = line_form.save()
        line._onchange_force_company_id()
        self.assertTrue(line.order_id)
        action_dict = line.action_sale_order_form()
        self.assertEqual(action_dict["res_id"], line.order_id.id)
        self.assertEqual(action_dict["res_model"], "sale.order")
