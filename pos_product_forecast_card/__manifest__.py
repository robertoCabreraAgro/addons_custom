{
    'name': 'POS Product Forecast Card',
    'version': '18.1.0',
    'category': 'Point of Sale',
    'summary': 'Displays a forecast card with predicted quantity in POS products',
    'description': """
        This module adds a small card to each POS product
        showing the forecasted quantity (virtual_available) visually.
        Allows configuration of which warehouses to include from the POS settings.
    """,
    'author': 'German, Jeziel',
    'depends': ['point_of_sale', 'stock'],
    'data': [
        'views/pos_config_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_product_forecast_card/static/src/js/custom_qty_modal.js',
            'pos_product_forecast_card/static/src/js/custom_qty_modal_loader.js',
            'pos_product_forecast_card/static/src/js/product_confirm_patch.js',
            'pos_product_forecast_card/static/src/js/product_card_forecast.js',
            'pos_product_forecast_card/static/src/js/product_screen_forecast_patch.js',
            'pos_product_forecast_card/static/src/xml/product_card_forecast.xml',
            'pos_product_forecast_card/static/src/css/product_card_forecast.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
