import os
import re
from typing import List, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class MarinAiAgent(models.Model):
    """AI Agent model for managing AI agents in the system."""

    _name = "marin.ai.agent"
    _description = "Marin AI Agent"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"

    name = fields.Char(string="Agent Name", required=True, tracking=True)
    sequence = fields.Integer(string="Sequence", default=10, help="Order of agent evaluation")
    intent = fields.Selection(
        [
            ("orchestrator", "Orchestrator"),
            ("inventory", "Inventory Agent"),
            ("sales", "Sales Agent"),
            ("chat", "Chat Agent"),
            ("custom", "Custom Agent"),
        ],
        string="Intent",
        required=True,
        tracking=True,
    )
    active = fields.Boolean(string="Active", default=True, tracking=True)

    # Configuration
    agent_model_id = fields.Many2one("marin.ai.agent.model", string="AI Model", required=True, tracking=True)
    context = fields.Text(
        string="Context",
        required=True,
        tracking=True,
        help="Prompt template with placeholders like {input}, {table_info}, etc.",
    )

    # Relations
    model_ids = fields.Many2many("ir.model", string="Models", help="Models/tables that this agent can access")
    prompt_ids = fields.One2many("marin.ai.prompt", "agent_id", string="Prompts", readonly=True)

    def _get_table_info(self, model_names: List[str]) -> str:
        """Get schema information for the given Odoo models using ORM metadata."""
        table_info = ""
        for model_name in model_names:
            try:
                if model_name not in self.env:
                    _logger.warning(f"Model '{model_name}' not found in registry")
                    continue

                model = self.env[model_name]
                table_name = model._table

                table_info += f"Table: {table_name} (Model: {model_name})\n"

                # Get field information
                fields_info = model.fields_get()
                for field_name, field_attrs in fields_info.items():
                    if field_attrs.get("store", True):  # Only stored fields
                        table_info += f"  - Column: {field_name} (Type: {field_attrs.get('type', 'unknown')})\n"
                table_info += "\n"

            except Exception as e:
                _logger.warning(f"Error getting info for model '{model_name}': {e}")
                continue

        return table_info

    def _validate_query(self, sql_query: str) -> str:
        """Validate that the query is a safe SELECT statement and add LIMIT if needed."""
        query = sql_query.strip()

        if not query.lower().startswith("select"):
            raise ValidationError("Invalid query: Only SELECT statements are allowed.")

        forbidden_keywords = [
            "insert",
            "update",
            "delete",
            "drop",
            "alter",
            "create",
            "truncate",
            "grant",
            "revoke",
            "commit",
            "rollback",
            "with",
        ]

        # Use regex to avoid false positives with word boundaries
        pattern = r"\b(" + "|".join(forbidden_keywords) + r")\b"
        if re.search(pattern, query.lower()):
            raise ValidationError("Invalid query: Contains forbidden keywords.")

        # Add LIMIT if not present to prevent massive data extraction
        if "limit" not in query.lower():
            query += " LIMIT 100"

        return query

    def _run_query(self, sql_query: str):
        """Execute a validated SQL query using Odoo's cursor and return results."""
        query = self._validate_query(sql_query)

        _logger.info(f"⚙️ Executing SQL:\n{query}\n")

        try:
            # Use Odoo's cursor for transaction safety
            self.env.cr.execute(query)
            return self.env.cr.dictfetchall()
        except Exception as e:
            _logger.error(f"💥 Error executing query: {e}")
            # Don't manually rollback - Odoo handles it when UserError is raised
            raise UserError(f"Query execution failed: {str(e)}")

    def _create_llm_instance(self):
        """Create LLM instance for this agent."""
        if not self.agent_model_id:
            raise UserError("No AI model configured for this agent.")

        api_key = os.getenv(self.agent_model_id.api_key_env_var)
        if not api_key:
            raise UserError(f"Environment variable {self.agent_model_id.api_key_env_var} not set.")

        if self.agent_model_id.provider == "google":
            return ChatGoogleGenerativeAI(
                model=self.agent_model_id.name,
                temperature=self.agent_model_id.temperature,
                google_api_key=api_key,
                max_output_tokens=self.agent_model_id.max_tokens,
            )
        else:
            raise UserError(f"Provider {self.agent_model_id.provider} not implemented yet.")

    def _get_tables(self) -> List[str]:
        """Get list of table names from model_ids relation."""
        if not self.model_ids:
            return []
        return [model.model for model in self.model_ids]

    def _create_sql_agent_chain(self):
        """Create SQL agent chain for this agent."""
        # Fix: Use existing _get_tables() method instead of non-existent _get_domain_tables()
        tables = self._get_tables()
        if not tables:
            raise UserError(f"No models configured for agent {self.name}")

        llm = self._create_llm_instance()
        table_info = self._get_table_info(tables)

        # Create prompt template from context
        prompt_template = PromptTemplate.from_template(self.context)

        # Create SQL generation chain without external SQLDatabase dependency
        sql_query_chain = (
            RunnablePassthrough.assign(table_info=lambda x: table_info) | prompt_template | llm | StrOutputParser()
        )

        # Get final response template
        final_template = self._get_final_response_template()
        answer_prompt = PromptTemplate.from_template(final_template)
        answer_chain = answer_prompt | llm | StrOutputParser()

        # Complete chain
        chain = (
            RunnablePassthrough.assign(question=lambda x: x["input"])
            .assign(sql_query=sql_query_chain)
            .assign(result=lambda x: self._run_query(x["sql_query"]))
            | answer_chain
        )
        return chain

    def _get_final_response_template(self):
        """Get final response template from prompt templates."""
        template = self.env["marin.ai.prompt.template"].search(
            [("category", "=", "final_response"), ("active", "=", True)], limit=1
        )

        if template:
            return template.prompt

        # Default final response template
        return """
Eres un asistente de Odoo amigable y servicial.
Tu tarea es tomar la pregunta original del usuario y los resultados de la base de datos y formular una respuesta clara, concisa y en lenguaje natural.

- Resume los hallazgos de forma amable.
- Si los resultados son una lista, formatéalos de manera legible.
- Si no hay resultados, informa al usuario educadamente.
- Responde siempre en el mismo idioma de la pregunta del usuario.

**Pregunta Original del Usuario:**
{question}

**Resultados de la Base de Datos:**
{result}

**Respuesta Final:**
"""

    def process_prompt_for_agent(self, user_input: str, **kwargs) -> str:
        """Process prompt through this specific agent."""
        self.ensure_one()

        if not self.active:
            raise UserError(f"Agent {self.name} is not active.")

        try:
            if self.intent in ["inventory", "sales", "custom"] and self.model_ids:
                # SQL-enabled agent
                chain = self._create_sql_agent_chain()
                response = chain.invoke({"input": user_input})
            else:
                # Chat/orchestrator agent
                llm = self._create_llm_instance()
                prompt = PromptTemplate.from_template(self.context)
                chain = prompt | llm | StrOutputParser()

                # Prepare context for chat agents
                invoke_data = {"user_input": user_input}
                if "history" in kwargs:
                    invoke_data["history"] = kwargs["history"]

                response = chain.invoke(invoke_data)

            return response

        except Exception as e:
            _logger.error(f"Error processing prompt with agent {self.name}: {e}", exc_info=True)
            raise UserError(f"Error processing request: {str(e)}")

    @api.model
    def process_prompt(self, user_input: str, chat_history: Optional[List] = None) -> str:
        """Main method to receive prompt and return response."""
        if not user_input or not user_input.strip():
            return "Please provide a valid question or prompt."

        if chat_history is None:
            chat_history = []

        prompt_record = None

        try:
            # Create prompt record for tracking
            prompt_record = self.env["marin.ai.prompt"].create(
                {
                    "prompt": user_input,
                    "user": self.env.user.id,
                }
            )

            # Step 1: Classify intent
            intent = self._classify_intent(user_input)

            # Step 2: Locate appropriate agent
            agent = self._locate_agent(intent)

            # Step 3: Send to agent for processing
            _logger.info(f"Routing to agent: {agent.name}")

            response = agent.process_prompt_for_agent(
                user_input,
                history="\n".join(
                    [
                        f"User: {item.get('user', '')}\nAssistant: {item.get('assistant', '')}"
                        for item in chat_history[-5:]
                    ]
                ),
            )

            # Update prompt record
            prompt_record.write(
                {"response": response, "agent_id": agent.id, "name": f"{agent.name} - {user_input[:30]}..."}
            )

            return response

        except Exception as e:
            error_msg = f"I encountered an error while processing your request: {str(e)}"
            _logger.error(f"Error processing prompt: {e}", exc_info=True)

            if prompt_record:
                prompt_record.write({"response": error_msg, "name": f"Error - {user_input[:30]}..."})

            return error_msg

    def _classify_intent(self, user_input: str) -> str:
        """Classify user intent using orchestrator agent."""
        orchestrator = self.search([("intent", "=", "orchestrator"), ("active", "=", True)], limit=1)

        if not orchestrator:
            # If no orchestrator, return CHAT as default
            return "CHAT"

        try:
            response = orchestrator.process_prompt_for_agent(user_input)
            return response.strip().upper()
        except Exception as e:
            _logger.warning(f"Intent classification failed: {e}")
            return "CHAT"

    def _locate_agent(self, intent: str):
        """Locate appropriate agent based on intent."""
        # Define intent to agent type mapping
        intent_mapping = {"INVENTORY_QUERY": "inventory", "SALES_QUERY": "sales", "CHAT": "chat"}

        # Find active agent of the determined type
        agent = self.search([("intent", "=", intent_mapping.get(intent, "chat")), ("active", "=", True)], limit=1)

        if not agent:
            # Fallback to chat agent
            agent = self.search([("intent", "=", "chat"), ("active", "=", True)], limit=1)

        if not agent:
            raise UserError("No active agents found to handle the request.")

        return agent
