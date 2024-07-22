from odoo.exceptions import UserError
from odoo.tests.common import tagged

from odoo.addons.point_of_sale.tests.common import TestPoSCommon


@tagged("post_install", "-at_install")
class TestPoSStock(TestPoSCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.LotObj = cls.env["stock.lot"]
        cls.StockQuantObj = cls.env["stock.quant"]
        cls.config = cls.basic_config
        cls.default_location = cls.config.picking_type_id.default_location_src_id
        cls.product_a = cls.create_product("Product 1", cls.categ_anglo, 10.0, 5.0)
        cls.product_a.tracking = "lot"
        cls.lot_p_a = cls.LotObj.create(
            {
                "name": "lot_product_1",
                "product_id": cls.product_a.id,
                "company_id": cls.company.id,
            }
        )
        cls.env.user.groups_id = [(4, cls.env.ref("marin.group_stock_inventory_adjustment").id)]
        cls.quant_p_a = cls.StockQuantObj.create(
            {
                "product_id": cls.product_a.id,
                "location_id": cls.default_location.id,
                "quantity": 10.0,
                "lot_id": cls.lot_p_a.id,
            }
        )
        cls.quant_p_a.action_apply_inventory()

    def test_01_pos_stock_availability(self):
        self.LotObj.get_available_lots_for_pos(self.product_a.id, self.company.id, self.config.id)
        # self.assertEqual(len(lots), 1)
        # self.assertEqual(lots[0].get("on_hand_qty"), 10)
        # self.assertEqual(lots[0].get("available_qty"), 10)
        # self.assertEqual(lots[0].get("id"), self.lot_p_a.id)
        # self.assertEqual(lots[0].get("name"), self.lot_p_a.name)

    def test_02_get_removal_strategies(self):
        strat = self.quant_p_a._get_removal_strategy_domain_order([], "fifo + priority", 1)[1]
        self.assertEqual(strat, "in_date ASC, removal_priority ASC, id")
        strat = self.quant_p_a._get_removal_strategy_domain_order([], "lifo + priority", 1)[1]
        self.assertEqual(strat, "in_date DESC, removal_priority ASC, id DESC")
        strat = self.quant_p_a._get_removal_strategy_domain_order([], "closest + priority", 1)[1]
        self.assertEqual(strat, "removal_priority ASC, location_id ASC, id DESC")
        strat = self.quant_p_a._get_removal_strategy_domain_order([], "fefo + priority", 1)[1]
        self.assertEqual(strat, "removal_date, removal_priority ASC, id")
        strat = self.quant_p_a._get_removal_strategy_domain_order([], "fifo", 1)[1]
        self.assertEqual(strat, "in_date ASC, id")
        _sortkey, reverse = self.quant_p_a._get_removal_strategy_sort_key("fifo + priority")
        self.assertFalse(reverse)
        _sortkey, reverse = self.quant_p_a._get_removal_strategy_sort_key("lifo + priority")
        self.assertTrue(reverse)
        _sortkey, reverse = self.quant_p_a._get_removal_strategy_sort_key("closest + priority")
        self.assertFalse(reverse)
        _sortkey, reverse = self.quant_p_a._get_removal_strategy_sort_key("fefo + priority")
        self.assertFalse(reverse)
        _sortkey, reverse = self.quant_p_a._get_removal_strategy_sort_key("fifo")
        self.assertFalse(reverse)

    def test_03_error_validate_quant(self):
        self.env.user.groups_id = [(3, self.env.ref("marin.group_stock_inventory_adjustment").id)]
        quant = self.StockQuantObj.create(
            {
                "product_id": self.product_a.id,
                "location_id": self.default_location.id,
                "quantity": 10.0,
                "lot_id": self.lot_p_a.id,
            }
        )
        with self.assertRaisesRegex(UserError, "Only a Inventory manager can validate an inventory adjustment."):
            quant.action_apply_inventory()
        self.env.user.groups_id = [(4, self.env.ref("marin.group_stock_inventory_adjustment").id)]
        quant.action_apply_inventory()

    def test_04_view_inventory(self):
        self.env.user.groups_id = [(3, self.env.ref("marin.group_stock_inventory_adjustment").id)]
        self.env.user.groups_id = [(3, self.env.ref("stock.group_stock_manager").id)]
        self.env.user.groups_id = [(4, self.env.ref("stock.group_stock_user").id)]
        action = self.quant_p_a.action_view_inventory()
        self.assertTrue(action.get("search_default_my_count"))
        self.env.user.groups_id = [(4, self.env.ref("stock.group_stock_manager").id)]
        self.env.user.groups_id = [(4, self.env.ref("marin.group_stock_inventory_adjustment").id)]
        quant = self.StockQuantObj.create(
            {
                "product_id": self.product_a.id,
                "location_id": self.default_location.id,
                "quantity": 10.0,
                "lot_id": self.lot_p_a.id,
            }
        )
        quant.action_apply_inventory()
        action = quant.action_view_inventory()
        self.assertFalse(action.get("search_default_my_count"))
