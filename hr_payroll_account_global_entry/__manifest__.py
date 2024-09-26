{
    "name": "Payroll Global Entry",
    "summary": """
    Allows to generate a journal entry for each payroll in a batch instead of a monthly accounting entry.""",
    "author": "Vauxoo",
    "website": "https://www.vauxoo.com",
    "license": "OPL-1",
    "category": "Accounting/Accounting",
    "version": "18.0.1.0.0",
    "depends": [
        "hr_payroll_account",
    ],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}
