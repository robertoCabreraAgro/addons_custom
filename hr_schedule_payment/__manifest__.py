{
    "name": "Hr Schedule Payment",
    "summary": """
    Allows to configure the payment days for payroll
    """,
    "author": "Vauxoo",
    "website": "https://www.vauxoo.com",
    "license": "OPL-1",
    "category": "Human Resources/Payroll",
    "version": "18.0.1.0.0",
    "depends": [
        "hr_payroll_account",
    ],
    "data": [
        "data/hr_schedule_payment_data.xml",
        "security/ir.model.access.csv",
        "views/hr_schedule_payment_views.xml",
        "views/hr_contract_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": True,
}
