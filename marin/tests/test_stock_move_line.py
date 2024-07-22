# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import Form

from odoo.addons.stock.tests.common import TestStockCommon


class TestStockMoveLine(TestStockCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.groups_id += cls.env.ref("stock.group_tracking_owner")
        cls.env.user.groups_id += cls.env.ref("stock.group_tracking_lot")
        cls.env.user.groups_id += cls.env.ref("stock.group_production_lot")
        cls.env.user.groups_id += cls.env.ref("stock.group_stock_multi_locations")
        cls.product = cls.env["product.product"].create(
            {
                "name": "Product A",
                "type": "product",
                "tracking": "lot",
                "categ_id": cls.env.ref("product.product_category_all").id,
            }
        )
        cls.shelf1 = cls.env["stock.location"].create(
            {
                "name": "Shelf 1",
                "usage": "internal",
                "location_id": cls.stock_location,
            }
        )
        cls.pack = cls.env["stock.quant.package"].create(
            {
                "name": "Pack A",
            }
        )
        cls.lot = cls.env["stock.lot"].create(
            {
                "product_id": cls.product.id,
                "name": "Lot 1",
                "company_id": cls.env.company.id,
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "The Owner",
                "email": "owner@example.com",
            }
        )

        cls.quant = cls.env["stock.quant"].create(
            {
                "product_id": cls.product.id,
                "location_id": cls.shelf1.id,
                "quantity": 10,
                "lot_id": cls.lot.id,
                "package_id": cls.pack.id,
                "owner_id": cls.partner.id,
            }
        )
        cls.picking_type_internal = cls.env["ir.model.data"]._xmlid_to_res_id("stock.picking_type_internal")
        cls.shelf2 = cls.env["stock.location"].create(
            {
                "name": "Shelf 2",
                "usage": "internal",
                "location_id": cls.stock_location,
            }
        )

    def test_01_move_line_location_availability(self):
        move = self.env["stock.move"].create(
            {
                "name": "Test move",
                "product_id": self.product.id,
                "product_uom": self.product.uom_id.id,
                "location_id": self.shelf1.id,
                "location_dest_id": self.shelf2.id,
                "product_uom_qty": 3.0,
            }
        )
        move_form = Form(move, view="stock.view_stock_move_operations")
        with move_form.move_line_ids.new() as ml:
            ml.quant_id = self.quant
        move = move_form.save()
        self.assertEqual(move.move_line_ids.lot_id, self.lot)
        self.assertEqual(move.move_line_ids.location_id, self.shelf1)
        self.assertEqual(move.move_line_ids.quantity, 3.0)
        self.assertEqual(move.move_line_ids.location_availability, 7.0)
        self.assertEqual(move.move_line_ids.location_dest_availability, 0.0)
        domain = [("id", "in", self.lot.ids)]
        self.assertEqual(move.move_line_ids.location_lot_domain, domain)
        move.picked = True
        move._action_done()
        move.move_line_ids._compute_location_availability()
        self.assertEqual(move.move_line_ids.location_availability, 7.0)
        self.assertEqual(move.move_line_ids.location_dest_availability, 3.0)

        move2 = self.env["stock.move"].create(
            {
                "name": "Test move 2",
                "product_id": self.product.id,
                "product_uom": self.product.uom_id.id,
                "location_id": self.shelf1.id,
                "location_dest_id": self.shelf2.id,
                "product_uom_qty": 3.0,
            }
        )
        move_form2 = Form(move2, view="stock.view_stock_move_operations")
        with move_form2.move_line_ids.new() as ml2:
            ml2.quant_id = self.quant
        move2 = move_form2.save()
        self.assertEqual(move2.move_line_ids.lot_id, self.lot)
        self.assertEqual(move2.move_line_ids.location_id, self.shelf1)
        self.assertEqual(move2.move_line_ids.quantity, 3.0)
        self.assertEqual(move2.move_line_ids.location_availability, 4.0)
        self.assertEqual(move2.move_line_ids.location_dest_availability, 3.0)
        move2.picked = True
        move2._action_done()
        move2.move_line_ids._compute_location_availability()
        self.assertEqual(move2.move_line_ids.location_availability, 4.0)
        self.assertEqual(move2.move_line_ids.location_dest_availability, 6.0)

        move3 = self.env["stock.move"].create(
            {
                "name": "Test move 3",
                "product_id": self.product.id,
                "product_uom": self.product.uom_id.id,
                "location_id": self.shelf1.id,
                "location_dest_id": self.shelf2.id,
                "product_uom_qty": 4.0,
            }
        )
        move_form3 = Form(move3, view="stock.view_stock_move_operations")
        with move_form3.move_line_ids.new() as ml3:
            ml3.quant_id = self.quant
        move3 = move_form3.save()
        self.assertEqual(move3.move_line_ids.lot_id, self.lot)
        self.assertEqual(move3.move_line_ids.location_id, self.shelf1)
        self.assertEqual(move3.move_line_ids.quantity, 4.0)
        self.assertEqual(move3.move_line_ids.location_availability, 0.0)
        self.assertEqual(move3.move_line_ids.location_dest_availability, 6.0)
        move3.picked = True
        move3._action_done()
        move3.move_line_ids._compute_location_availability()
        self.assertEqual(move3.move_line_ids.location_availability, 0.0)
        self.assertEqual(move3.move_line_ids.location_dest_availability, 10.0)
