from odoo import models, fields, api
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    """
    Extends the POS configuration to support product forecast card features.
    Allows selection of warehouses, toggling forecast card, and exporting config to POS frontend.
    """
    _inherit = 'pos.config'

    forecast_warehouse_indexes = fields.Char(
        string="Selected Warehouse Indexes",
        help="Comma-separated indexes of selected warehouses for forecast."
    )

    # Field to select warehouses to include in forecast
    forecast_warehouse_ids = fields.Many2many(
        'stock.warehouse',
        'pos_config_forecast_warehouse_rel',
        'pos_config_id',
        'warehouse_id',
        string='Warehouses for Forecast',
        help='Select the warehouses to include in the product forecast calculation',
        readonly=False
    )

    # Field to show/hide forecast card
    show_product_forecast = fields.Boolean(
        string='Show Product Forecast',
        help='Displays a card with forecasted quantity in POS products',
        readonly=False
    )


    def export_as_JSON(self):
        """
        Export POS configuration including forecast settings to the frontend as JSON.
        Returns:
            dict: Configuration values for the POS frontend.
        """
        res = super().export_as_JSON()
        # Export only the indexes of selected warehouses
        res['forecast_warehouse_indexes'] = self.forecast_warehouse_indexes
        res['show_product_forecast'] = self.show_product_forecast
        # If no warehouses selected, frontend should interpret as "all warehouses"
        return res

    @api.constrains('forecast_warehouse_indexes')
    def _check_forecast_warehouse_indexes(self):
        """
        Ensure forecast_warehouse_indexes contains only valid, unique, comma-separated integers.
        """
        for rec in self:
            if rec.forecast_warehouse_indexes:
                indexes = [i.strip() for i in rec.forecast_warehouse_indexes.split(',') if i.strip()]
                if len(indexes) != len(set(indexes)):
                    raise ValidationError("Duplicate warehouse indexes are not allowed in forecast_warehouse_indexes.")
                for idx in indexes:
                    if not idx.isdigit():
                        raise ValidationError("All forecast warehouse indexes must be integers.")

    @api.constrains('show_product_forecast', 'forecast_warehouse_ids')
    def _check_show_product_forecast_warehouses(self):
        """
        If show_product_forecast is enabled, allow forecast_warehouse_ids to be empty.
        An empty value means 'all warehouses' (placeholder behavior).
        No ValidationError is raised if empty.
        """
        # No validation needed: empty = all warehouses (valid)
        pass

    def _pos_ui_models_to_load(self):
        res = super()._pos_ui_models_to_load()
        if 'stock.production.lot' not in res:
            res.append('stock.production.lot')
        return res

    def _loader_params_stock_production_lot(self):
        return {
            'search_params': {
                'domain': [],
                'fields': ['id', 'name', 'product_id', 'life_date', 'expiration_date', 'use_date', 'removal_date'],
            }
        }

    def _get_pos_ui_stock_production_lot(self, params):
        lots = self.env['stock.production.lot'].search_read(
            params['search_params']['domain'],
            params['search_params']['fields']
        )
        return lots
