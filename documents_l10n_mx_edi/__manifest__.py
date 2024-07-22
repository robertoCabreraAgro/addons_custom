{
    "name": "CFDI file Management",
    "version": "1.0",
    "summary": """Download CFDI files from SAT
        portal for its further processing and management.""",
    "category": "Localization/Mexico",
    "author": "Jarsa,Vauxoo",
    "depends": [
        "documents",
        "l10n_mx_edi",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/ir_cron_data.xml",
        "data/documents_data.xml",
        "data/workflow_data.xml",
        "views/res_config_settings_views.xml",
        "views/documents_views.xml",
        "views/account_move_line_views.xml",
        "views/account_payment_views.xml",
        "views/l10n_mx_edi_esignature_views.xml",
        "wizard/sat_sync_wizard.xml",
        "wizard/mx_edi_to_record_wizard.xml",
    ],
    "installable": True,
    "license": "OPL-1",
}
