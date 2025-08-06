{
    'name': 'Marin AI',
    'version': '1.0',
    'category': 'Artificial Intelligence',
    'summary': 'AI functionality for Marin ERP system',
    'author': 'AgroMarin',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/marin_ai_agent_views.xml',
        'views/marin_ai_agent_model_views.xml',
        'views/marin_ai_prompt_template_views.xml',
    ],
    'installable': True,
    'auto_install': False,
}
