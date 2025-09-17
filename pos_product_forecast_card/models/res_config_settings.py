from odoo import fields, models, api


class ResConfigSettings(models.TransientModel):
    """
    Extends res.config.settings to allow configuration of product forecast card for POS.
    Handles default values and mapping of warehouse indexes to IDs for forecast settings.
    """
    _inherit = ["res.config.settings", "pos.load.mixin"]

    forecast_warehouse_ids = fields.Many2many(
        'stock.warehouse',
        'res_config_forecast_warehouse_rel',
        'config_id',
        'warehouse_id',
        string="Warehouses for forecast",
        help="Warehouses to consider for product forecast in POS."
    )
    forecast_warehouse_indexes = fields.Char(
        string="Selected Warehouse Indexes",
        help="Comma-separated indexes of selected warehouses for forecast."
    )

    show_product_forecast = fields.Boolean(
        string="Product Forecast",
        help="Show product forecast quantities in POS",
    )


    @api.model
    def default_get(self, fields):
        """
        Get default values for the settings, using POS config context if available.
        Args:
            fields (list): List of fields to get defaults for.
        Returns:
            dict: Default values for the settings.
        """
        res = super().default_get(fields)
        pos_config_id = self.env.context.get('default_pos_config_id')
        if pos_config_id:
            pos_config = self.env['pos.config'].browse(pos_config_id)
            res['forecast_warehouse_indexes'] = pos_config.forecast_warehouse_indexes
            res['forecast_warehouse_ids'] = [(6, 0, pos_config.forecast_warehouse_ids.ids)]
            res['show_product_forecast'] = pos_config.show_product_forecast
        return res

    def get_values(self):
        """
        Get values for the settings, mapping warehouse indexes to IDs.
        Returns:
            dict: Values for the settings with resolved warehouse IDs.
        """
        res = super().get_values()
        pos_config = self.pos_config_id
        if pos_config:
            all_warehouses = self.env['stock.warehouse'].search([])
            selected_ids = []
            if pos_config.forecast_warehouse_indexes:
                try:
                    indexes = [int(idx) for idx in pos_config.forecast_warehouse_indexes.split(',') if idx.strip()]
                    for idx in indexes:
                        if 0 <= idx < len(all_warehouses):
                            selected_ids.append(all_warehouses[idx].id)
                except Exception as e:
                    selected_ids = []
            else:
                # Si no hay almacenes seleccionados, usar todos
                selected_ids = all_warehouses.ids
            res.update(
                forecast_warehouse_ids=selected_ids,
                forecast_warehouse_indexes=pos_config.forecast_warehouse_indexes,
                show_product_forecast=pos_config.show_product_forecast,
            )
        return res

    def set_values(self):
        super().set_values()
        pos_config = self.pos_config_id
        if pos_config:
            # Calcular los índices de los almacenes seleccionados
            all_warehouses = self.env['stock.warehouse'].search([])
            selected_ids = self.forecast_warehouse_ids.ids
            indexes = []
            for idx, wh in enumerate(all_warehouses):
                if wh.id in selected_ids:
                    indexes.append(str(idx))
            indexes_str = ','.join(indexes)
            pos_config.forecast_warehouse_ids = self.forecast_warehouse_ids
            pos_config.forecast_warehouse_indexes = indexes_str
            pos_config.show_product_forecast = self.show_product_forecast

    @api.onchange('pos_config_id')
    def _onchange_pos_config_id(self):
        if self.pos_config_id:
            self.forecast_warehouse_ids = self.pos_config_id.forecast_warehouse_ids
            self.forecast_warehouse_indexes = self.pos_config_id.forecast_warehouse_indexes
            self.show_product_forecast = self.pos_config_id.show_product_forecast

    @api.onchange('show_product_forecast', 'forecast_warehouse_ids', 'forecast_warehouse_indexes')
    def _onchange_forecast_fields(self):
        pass