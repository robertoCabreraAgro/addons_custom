{
    "name": "Hr Payroll Rule in Account Entry",
    "summary": """
    Allow reference the salary rule in the journal entry
    """,
    "author": "Vauxoo",
    "website": "https://www.vauxoo.com",
    "license": "OPL-1",
    "category": "Human Resources/Payroll",
    "version": "saas~18.1.1.0.0",
    "depends": [
        "hr_payroll_account",
    ],
    "data": [
        "views/hr_salary_rule_views.xml",
    ],
    "demo": [],
    "installable": True,
    "auto_install": False,
}
