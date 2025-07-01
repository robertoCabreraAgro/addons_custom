{
    "name": "Telegram Bot",
    "version": "1.0",
    "category": "Technical",
    "summary": "Module to use telegram bot for Odoo processes.",
    "license": "OPL-1",
    "author": "German Loredo Becerra",
    "depends": [
        "account_move_operation",
        "base_approval",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/approval_category_views.xml",
        "views/approval_request_views.xml",
        "views/res_partner_views.xml",
        "views/telegram_bot_views.xml",
    ],
    "installable": True,
    "application": False,
}
