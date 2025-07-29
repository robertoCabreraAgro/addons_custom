{
    "name": "Project Task Description Template",
    "summary": "Add a description template to project tasks",
    "version": "saas~18.2.0.0.1",
    "category": "Project Management",
    "author": "Jarsa, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/project",
    "license": "LGPL-3",
    "installable": True,
    "depends": ["project"],
    "data": [
        "security/ir.model.access.csv",
        "security/ir_rule_data.xml",
        "views/project_task_view.xml",
        "views/project_task_description_template_view.xml",
    ],
    "installable": True,
}
