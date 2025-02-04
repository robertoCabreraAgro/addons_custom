{
    "name": "Bank Dispersion",
    "summary": """Base module to generate the bank dispersion from payslips batch""",
    "author": "Vauxoo",
    "website": "https://www.vauxoo.com",
    "license": "OPL-1",
    "category": "Human Resources/Payroll",
    "version": "saas~18.1.1.0.0",
    "depends": [
        "hr_payroll",
    ],
    "data": [
        "data/ir_config_parameter_data.xml",
        "security/res_groups_security.xml",
        "views/hr_payslip_run_views.xml",
    ],
}
