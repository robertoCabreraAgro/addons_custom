{
    "name": "Hr Payroll: Payslip inputs batch",
    "summary": """
    Allow define the payroll inputs in batch
    """,
    "author": "Vauxoo",
    "website": "https://www.vauxoo.com",
    "license": "OPL-1",
    "category": "Human Resources/Payroll",
    "version": "saas~18.4.0.0.1",
    "depends": [
        "hr_payroll",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizards/hr_payslip_input_batch_employee_views.xml",
        "views/hr_payslip_input_batch_detail_views.xml",
        "views/hr_payslip_input_batch_views.xml",
        "views/hr_payslip_input_type_views.xml",
        "views/hr_payslip_views.xml",
    ],
}
