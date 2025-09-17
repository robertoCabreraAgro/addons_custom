from odoo import http
from odoo.http import request

class PosProductForecastCardWarehouseController(http.Controller):
    @http.route('/pos_product_forecast_card/get_locations_with_stock', type='json', auth='user')
    def get_locations_with_stock(self, warehouse_id, product_id):
        return request.env['pos.warehouse.api'].get_locations_with_stock(warehouse_id, product_id)
    @http.route('/pos_product_forecast_card/get_warehouses_with_stock', type='json', auth='user')
    def get_warehouses_with_stock(self, product_id):
        return request.env['pos.warehouse.api'].get_warehouses_with_stock(product_id)
    @http.route('/pos_product_forecast_card/get_warehouses', type='json', auth='user')
    def get_warehouses(self):
        return request.env['pos.warehouse.api'].get_warehouses()
