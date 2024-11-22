{
    "name": "Stock Quant Relocate",
    "version": "18.0.1.0.0",
    "author": "Julius Network Solutions, "
        "BCIM,"
        "Camptocamp,"
        "Odoo Community Association (OCA)",
    "summary": "This module allows to move all stock "
        "in a stock location to an other one.",
    "website": "https://github.com/OCA/stock-logistics-warehouse",
    "license": "AGPL-3",
    "depends": ["stock"],
    "category": "Stock",
    "data": [
        "security/ir.model.access.csv",
        "views/stock_quant_view.xml",
        "views/stock_picking_type_views.xml",
        "views/stock_picking_views.xml",
        "wizard/stock_relocate_views.xml",
    ],
    "post_init_hook": "enable_multi_locations",
}
