{
    "name": "Marin AI",
    "version": "1.0",
    "category": "Artificial Intelligence",
    "summary": "AI functionality for Marin ERP system",
    "author": "AgroMarin",
    "depends": ["base", "mail", "stock", "sale", "product"],
    "external_dependencies": {
        "python": [
            "langchain-google-genai",
            "langchain-core",
            "cryptography",
        ]
    },
    "data": [
        "security/res_groups_security.xml",
        "security/ir.model.access.csv",
        "security/ir_rule_security.xml",
        "data/ir_sequence_data.xml",
        "data/marin_ai_agent_model_data.xml",
        "data/marin_ai_prompt_template_data.xml",
        "data/marin_ai_agent_data.xml",
        "views/marin_ai_agent_views.xml",
        "views/marin_ai_agent_model_views.xml",
        "views/marin_ai_prompt_template_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}
