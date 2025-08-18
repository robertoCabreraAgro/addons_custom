{
    "name": "Mexico - Multiple Fiscal Regimes",
    "version": "saas~18.4.0.0.1",
    "category": "Accounting/Localizations",
    "summary": "Allow multiple fiscal regimes per partner in Mexican localization",
    "description": """
        This module extends the Mexican localization to support multiple fiscal regimes
        per partner, allowing dynamic selection of fiscal regime in invoices.

        Features:
        - New fiscal regime model for better management
        - Multiple fiscal regimes per partner
        - Dynamic fiscal regime selection in invoices
        - Proper domain constraints and validations
        - CFDI generation with selected fiscal regime
        - Migration from selection field to Many2one
    """,
    "author": "Agro Marin",
    "website": "https://www.agromarin.mx",
    "depends": [
        "l10n_mx_edi",
        "account",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/l10n_mx_edi_fiscal_regime_data.xml",
        "views/l10n_mx_edi_fiscal_regime_views.xml",
        "views/res_partner_views.xml",
        "views/account_journal_views.xml",
        "views/account_move_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "auto_install": False,
    "application": False,
}
