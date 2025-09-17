from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError

class TestPosProductForecastCard(TransactionCase):
    """Test input validation and config logic for POS Product Forecast Card."""

    def setUp(self):
        super().setUp()
        self.PosConfig = self.env['pos.config']
        self.Warehouse = self.env['stock.warehouse']
        # Create two warehouses for testing
        self.wh1 = self.Warehouse.create({'name': 'Test Warehouse 1', 'code': 'TWH1'})
        self.wh2 = self.Warehouse.create({'name': 'Test Warehouse 2', 'code': 'TWH2'})

    def test_forecast_warehouse_indexes_unique(self):
        config = self.PosConfig.create({
            'name': 'Test POS',
            'forecast_warehouse_indexes': '1,2,2',
            'show_product_forecast': True,
        })
        with self.assertRaises(ValidationError):
            config._check_forecast_warehouse_indexes()

    def test_forecast_warehouse_indexes_numeric(self):
        config = self.PosConfig.create({
            'name': 'Test POS',
            'forecast_warehouse_indexes': '1,a,3',
            'show_product_forecast': True,
        })
        with self.assertRaises(ValidationError):
            config._check_forecast_warehouse_indexes()

    def test_show_product_forecast_allows_empty_warehouses(self):
        config = self.PosConfig.create({
            'name': 'Test POS',
            'show_product_forecast': True,
            'forecast_warehouse_ids': [(6, 0, [])],
        })
        # Should not raise, empty means all warehouses
        config._check_show_product_forecast_warehouses()

    def test_valid_config(self):
        config = self.PosConfig.create({
            'name': 'Test POS',
            'show_product_forecast': True,
            'forecast_warehouse_ids': [(6, 0, [self.wh1.id, self.wh2.id])],
            'forecast_warehouse_indexes': '1,2',
        })
        # Should not raise
        config._check_forecast_warehouse_indexes()
        config._check_show_product_forecast_warehouses()
