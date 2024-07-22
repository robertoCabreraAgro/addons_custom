{
    "name": "Hr Payroll: Payslip lines pivot report",
    "summary": """
    Enable the pivot report for the payslips lines
    """,
    "author": "Vauxoo",
    "website": "https://www.vauxoo.com",
    "license": "OPL-1",
    "category": "Human Resources/Payroll",
    "version": "17.5.1.0.0",
    "depends": [
        "hr_payroll",
    ],
    "data": [
        "views/hr_payslip_line_views.xml",
        "views/hr_payslip_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}
