from odoo import models, fields, api

class PosWarehouseApi(models.AbstractModel):

    @api.model
    def get_locations_with_stock(self, warehouse_id, product_id):
        warehouse = self.env['stock.warehouse'].browse(warehouse_id)
        product = self.env['product.product'].browse(product_id)
        # Tomar la ubicación principal del almacén
        parent_location = warehouse.lot_stock_id
        # Buscar ubicaciones hijas directas (puedes ajustar domain para incluir subniveles)
        locations = self.env['stock.location'].search([
            ('location_id', '=', parent_location.id),
            ('usage', '=', 'internal')
        ])
        result = []
        for loc in locations:
            qty = product.with_context({'location': loc.id}).virtual_available
            result.append({
                'id': loc.id,
                'name': loc.display_name,
                'forecasted_quantity': qty,
            })
        return result

    @api.model
    def get_warehouses_with_stock(self, product_id):
        warehouses = self.env['stock.warehouse'].search([])
        product = self.env['product.product'].browse(product_id)
        result = []
        for w in warehouses:
            location = w.lot_stock_id
            qty = product.with_context({'location': location.id}).virtual_available
            result.append({
                'id': w.id,
                'name': w.display_name,
                'forecasted_quantity': qty,
            })
        return result
    _name = 'pos.warehouse.api'
    _description = 'POS Warehouses API'

    @api.model
    def get_warehouses(self):
        warehouses = self.env['stock.warehouse'].search([])
        # Dummy forecasted_quantity = 0, adjust as needed
        return [{
            'id': w.id,
            'name': w.display_name,
            'forecasted_quantity': 0
        } for w in warehouses]
