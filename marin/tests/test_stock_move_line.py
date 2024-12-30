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
