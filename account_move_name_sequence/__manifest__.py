
{
    "name": "Account Move Number Sequence",
    "version": "saas~18.1.1.0.5",
    "category": "Accounting",
    "license": "AGPL-3",
    "summary": "Generate journal entry number from sequence",
    "author": "Akretion,Vauxoo,Odoo Community Association (OCA)",
    "maintainers": ["alexis-via", "moylop260", "luisg123v"],
    "website": "https://github.com/OCA/account-financial-tools",
    "depends": [
        "account",
    ],
    "demo": [
        "demo/ir_sequence_demo.xml",
        "demo/account_journal_demo.xml",
    ],
    "data": [
        "views/account_journal_views.xml",
        "views/account_move_views.xml",
        "security/ir.model.access.csv",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
}
