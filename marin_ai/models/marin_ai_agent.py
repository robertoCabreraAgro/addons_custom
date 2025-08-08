import logging
import os
import re
from datetime import datetime, timedelta
from typing import List, Optional
import json

from odoo import models, fields, api, tools
from odoo.exceptions import ValidationError, UserError

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
        help="Prompt template with placeholders like {input}, {table_info}, {limit}, etc.",
    )

    # Relations
    model_ids = fields.Many2many("ir.model", string="Models", help="Models/tables that this agent can access")
    prompt_ids = fields.One2many("marin.ai.prompt", "agent_id", string="Prompts", readonly=True)

    # Security tracking
    max_query_limit = fields.Integer(
        string="Max Query Limit", default=100, help="Maximum number of records this agent can return in a single query"
    )
    queries_per_minute = fields.Integer(
        string="Queries Per Minute", default=10, help="Rate limit for queries per minute per user"
    )
    last_security_check = fields.Datetime(string="Last Security Check", readonly=True)
    security_violations_count = fields.Integer(string="Security Violations", readonly=True, default=0)

    # Dashboard computed fields
    prompt_count = fields.Integer(string="Prompts Processed", compute="_compute_prompt_count", store=False)
    prompts_today = fields.Integer(string="Prompts Today", compute="_compute_prompts_today", store=False)
    prompts_this_week = fields.Integer(string="Prompts This Week", compute="_compute_prompts_this_week", store=False)

    @api.model
    @tools.ormcache("model_names")
    def _get_table_info(self, model_names):
        """Get schema information for the given Odoo models using ORM metadata.

        Args:
            model_names (tuple): Tuple of model names (hashable for cache)

        Returns:
            str: Formatted table schema information
        """
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

    def write(self, vals):
        """Override write to clear cache when model_ids change."""
        result = super().write(vals)
        if "model_ids" in vals:
            self.env.registry.clear_cache()
        return result

    def _validate_query(self, sql_query: str) -> str:
        """Enhanced SQL validation with comprehensive security checks."""
        if not sql_query:
            raise ValidationError(self.env._("Query cannot be empty."))

        query = sql_query.strip()

        # Basic SELECT validation
        if not query.lower().startswith("select"):
            raise ValidationError(self.env._("Invalid query: Only SELECT statements are allowed."))

        # Comprehensive forbidden keywords list
        forbidden_keywords = [
            # Data modification
            "insert",
            "update",
            "delete",
            "truncate",
            "merge",
            "upsert",
            # Schema modification
            "drop",
            "alter",
            "create",
            "rename",
            # Access control
            "grant",
            "revoke",
            "deny",
            # Transaction control
            "commit",
            "rollback",
            "begin",
            "transaction",
            "savepoint",
            # System functions
            "execute",
            "exec",
            "call",
            "do",
            # Stored procedures (various databases)
            "xp_",
            "sp_",
            "sys.",
            "information_schema.",
            # File operations
            "load_file",
            "into outfile",
            "into dumpfile",
            "bulk insert",
            # Database-specific dangerous functions
            "pg_read_file",
            "pg_ls_dir",
            "copy",
            # Union-based injections prevention
            "@@",
            "char(",
            "chr(",
            "ascii(",
            "substring(",
        ]

        # Enhanced regex pattern with word boundaries and case insensitivity
        pattern = r"\b(" + "|".join(re.escape(kw) for kw in forbidden_keywords) + r")\b"
        if re.search(pattern, query.lower()):
            raise ValidationError(self.env._("Invalid query: Contains forbidden keywords or functions."))

        # Comprehensive comment detection
        comment_patterns = [
            r"--.*",  # SQL line comments
            r"/\*.*?\*/",  # SQL block comments
            r"#.*",  # MySQL comments
            r";\s*\w+",  # Statement terminators followed by additional commands (not just whitespace)
        ]

        for pattern in comment_patterns:
            if re.search(pattern, query, re.DOTALL):
                raise ValidationError(self.env._("Invalid query: Comments and command separators are not allowed."))

        # Check for suspicious patterns
        suspicious_patterns = [
            r"union\s+select",  # Union-based injection
            r";\s*select",  # Stacked queries
            r"waitfor\s+delay",  # Time-based attacks
            r"benchmark\s*\(",  # MySQL benchmark attacks
            r"sleep\s*\(",  # Sleep-based attacks
            r"load_file\s*\(",  # File reading
            r"into\s+(outfile|dumpfile)",  # File writing
        ]

        for pattern in suspicious_patterns:
            if re.search(pattern, query.lower()):
                raise ValidationError(self.env._("Invalid query: Suspicious SQL pattern detected."))

        # Validate table access against whitelist
        query = self._validate_table_access(query)

        # Enhanced LIMIT validation and enforcement
        query = self._enforce_result_limits(query)

        # Update security check timestamp
        self.sudo().write({"last_security_check": fields.Datetime.now()})

        return query

    def _validate_table_access(self, query: str) -> str:
        """Validate that query only accesses authorized tables."""
        if not self.model_ids:
            raise ValidationError(self.env._("No authorized tables configured for this agent."))

        # Get allowed table names from configured models
        allowed_tables = self._get_allowed_tables()

        if not allowed_tables:
            raise ValidationError(self.env._("No valid tables found in agent configuration."))

        # Extract table names from query using regex
        found_tables = self._extract_tables_from_query(query)

        # Check if all found tables are in whitelist
        unauthorized_tables = found_tables - allowed_tables
        if unauthorized_tables:
            # Log security violation
            self.sudo().write({"security_violations_count": self.security_violations_count + 1})
            _logger.warning(
                f"Security violation: Agent {self.id} attempted to access unauthorized tables: {unauthorized_tables}"
            )
            raise ValidationError(
                self.env._("Query accesses unauthorized tables: %s") % ", ".join(unauthorized_tables)
            )

        return query

    @tools.ormcache("self")
    def _get_allowed_tables(self):
        """Get set of allowed table names for this agent (cached)."""
        allowed_tables = set()
        for model in self.model_ids:
            try:
                if model.model in self.env:
                    table_name = self.env[model.model]._table
                    allowed_tables.add(table_name.lower())
            except Exception:
                continue
        return allowed_tables

    def _extract_tables_from_query(self, sql_query):
        """Extracts table names from SQL query as a set, ignoring aliases.
        
        Args:
            sql_query (str): SQL query to extract table names from
            
        Returns:
            set: Set of table names found
        """
        pattern = r'(?:^|[\s\n])(?:FROM|(?:INNER\s+|LEFT\s+|RIGHT\s+|FULL\s+|CROSS\s+)?JOIN)\s+([a-zA-Z_][a-zA-Z0-9_.]*)\s*(?:\s+(?:AS\s+)?[a-zA-Z_][a-zA-Z0-9_]*)?'
        
        tables = set()
        for match in re.finditer(pattern, sql_query, re.IGNORECASE | re.MULTILINE):
            # Skip if inside a function (has unclosed parenthesis before)
            context = sql_query[max(0, match.start() - 10):match.start()].upper()
            if '(' in context and ')' not in context:
                continue
                
            table_name = match.group(1).split('.')[-1]  # Take only table name if schema.table
            tables.add(table_name)
        
        return tables

    def _enforce_result_limits(self, query: str) -> str:
        """Enforce result size limits and add LIMIT if missing."""
        query_lower = query.lower()

        # Use agent-specific limits or defaults
        MAX_LIMIT = min(self.max_query_limit or 100, 1000)  # Never exceed 1000
        DEFAULT_LIMIT = min(self.max_query_limit or 100, 100)

        # Check if LIMIT is already present
        limit_match = re.search(r"\blimit\s+(\d+)", query_lower)

        if limit_match:
            limit_value = int(limit_match.group(1))
            if limit_value > MAX_LIMIT:
                # Replace with maximum allowed limit
                query = re.sub(r"\blimit\s+\d+", f"LIMIT {MAX_LIMIT}", query, flags=re.IGNORECASE)
                _logger.warning(f"Query limit reduced from {limit_value} to {MAX_LIMIT}")
        else:
            # Add default limit, removing trailing semicolon if present
            query = query.rstrip(';').rstrip()
            query += f" LIMIT {DEFAULT_LIMIT}"

        return query

    def _run_query(self, sql_query: str):
        """Execute a validated SQL query with rate limiting and security controls."""
        # Apply rate limiting
        self._check_rate_limit()

        query = self._validate_query(sql_query)

        # Log query execution without exposing sensitive data
        query_hash = hash(query)
        _logger.info(f"Agent {self.id} executing query (hash: {query_hash})")

        try:
            # Record query execution for rate limiting
            self._record_query_execution()

            # Use Odoo's cursor for transaction safety
            self.env.cr.execute(query)
            results = self.env.cr.dictfetchall()

            # Log successful execution with result count
            _logger.info(f"Query executed successfully, returned {len(results)} records")

            return results

        except Exception as e:
            _logger.error(f"Query execution failed for agent {self.id}: {type(e).__name__}")
            # Don't log the actual error message to avoid information disclosure
            raise UserError(self.env._("Query execution failed. Please check your query syntax."))

    def _check_rate_limit(self):
        """Check if user has exceeded query rate limits."""
        current_user = self.env.user

        # Get rate limit configuration (queries per minute)
        queries_per_minute = self.queries_per_minute or 10
        if current_user.has_group("marin_ai.group_marin_ai_admin"):
            queries_per_minute = min(queries_per_minute * 3, 50)  # Higher limit for admins, capped at 50

        # Use system parameters for rate limiting (database-based approach)
        param_key = f"marin_ai.rate_limit_{current_user.id}_{self.id}"
        
        # Get cached query timestamps
        cached_data = self.env["ir.config_parameter"].sudo().get_param(param_key, "[]")
        try:
            query_times = [datetime.fromisoformat(ts) for ts in json.loads(cached_data)]
        except (json.JSONDecodeError, ValueError):
            query_times = []

        # Remove timestamps older than 1 minute
        cutoff_time = datetime.now() - timedelta(minutes=1)
        recent_queries = [ts for ts in query_times if ts > cutoff_time]

        # Check if limit exceeded
        if len(recent_queries) >= queries_per_minute:
            raise UserError(self.env._("Rate limit exceeded. Please wait before executing more queries."))

    def _record_query_execution(self):
        """Record query execution timestamp for rate limiting."""
        current_user = self.env.user
        param_key = f"marin_ai.rate_limit_{current_user.id}_{self.id}"

        # Get existing timestamps
        cached_data = self.env["ir.config_parameter"].sudo().get_param(param_key, "[]")
        try:
            query_times = [datetime.fromisoformat(ts) for ts in json.loads(cached_data)]
        except (json.JSONDecodeError, ValueError):
            query_times = []

        # Add current timestamp
        query_times.append(datetime.now())

        # Keep only last hour of data
        cutoff_time = datetime.now() - timedelta(hours=1)
        query_times = [ts for ts in query_times if ts > cutoff_time]

        # Store back in system parameters
        timestamps_str = json.dumps([ts.isoformat() for ts in query_times])
        self.env["ir.config_parameter"].sudo().set_param(param_key, timestamps_str)

    def _create_llm_instance(self):
        """Create LLM instance for this agent with secure API key handling."""
        if not self.agent_model_id:
            raise UserError(self.env._("No AI model configured for this agent."))

        if not self.agent_model_id.api_key_env_var:
            raise UserError(self.env._("No API key environment variable configured for the AI model."))
        # Get API key using secure method
        api_key = self.agent_model_id.get_api_key()
        if not api_key:
            _logger.error(f"Missing API key for agent {self.id}, model {self.agent_model_id.name}")
            raise UserError(self.env._("API key not configured. Please contact system administrator."))

        try:
            if self.agent_model_id.provider == "google":
                # Log model initialization without exposing sensitive data
                _logger.info(f"Initializing Google AI model for agent {self.id}")
                from langchain_google_genai import ChatGoogleGenerativeAI

                return ChatGoogleGenerativeAI(
                    model=self.agent_model_id.name,
                    temperature=self.agent_model_id.temperature,
                    google_api_key=api_key,
                    max_output_tokens=self.agent_model_id.max_tokens,
                )
            else:
                raise UserError(self.env._("Provider '%s' not implemented yet.") % self.agent_model_id.provider)
        except Exception as e:
            # Log error without exposing sensitive information
            _logger.error(f"Failed to create LLM instance for agent {self.id}: {type(e).__name__}")
            raise UserError(self.env._("Failed to initialize AI model. Please check configuration."))

    def _get_tables(self) -> List[str]:
        """Get list of table names from model_ids relation."""
        if not self.model_ids:
            return []
        return [model.model for model in self.model_ids]

    def _create_sql_agent_chain(self):
        """Create SQL agent chain for this agent."""
        model_names = self._get_tables()
        if not model_names:
            raise UserError(f"No models configured for agent {self.name}")

        llm = self._create_llm_instance()
        # Convert to tuple for caching (lists are not hashable)
        table_info = self._get_table_info(tuple(sorted(model_names)))

        # Create prompt template from context with limit placeholder replacement
        from langchain_core.prompts import PromptTemplate

        # Replace {limit} placeholder with max_query_limit value
        limit_value = self.max_query_limit or 100
        context_with_limit = self.context.replace("{limit}", str(limit_value))
        prompt_template = PromptTemplate.from_template(context_with_limit)

        # Create SQL generation chain without external SQLDatabase dependency
        from langchain_core.runnables import RunnablePassthrough
        from langchain_core.output_parsers import StrOutputParser

        sql_query_chain = (
            RunnablePassthrough.assign(table_info=lambda x: table_info) | prompt_template | llm | StrOutputParser()
        )

        # Get final response template
        final_template = self._get_final_response_template()
        answer_prompt = PromptTemplate.from_template(final_template)
        answer_chain = answer_prompt | llm | StrOutputParser()

        # Create a closure that captures the agent instance
        def execute_sql_query(x):
            """Execute SQL query with proper context."""
            # Clean SQL query from markdown formatting
            sql_query = x["sql_query"].strip()
            if sql_query.startswith("```sql"):
                sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
            elif sql_query.startswith("```"):
                sql_query = sql_query.replace("```", "").strip()
            
            return self._run_query(sql_query)

        # Complete chain
        chain = (
            RunnablePassthrough.assign(question=lambda x: x["input"])
            .assign(sql_query=sql_query_chain)
            .assign(result=execute_sql_query)
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

    def execute(self, user_input: str, **kwargs) -> str:
        """Process prompt through this specific agent."""
        self.ensure_one()

        if not self.active:
            raise UserError(self.env._("Agent '%s' is not active.") % self.name)

        if not user_input or not user_input.strip():
            raise ValidationError(self.env._("Input cannot be empty."))
        try:
            if self.intent in ["inventory", "sales", "custom"] and self.model_ids:
                # SQL-enabled agent
                chain = self._create_sql_agent_chain()
                response = chain.invoke({"input": user_input})
            else:
                # Chat/orchestrator agent
                llm = self._create_llm_instance()
                from langchain_core.prompts import PromptTemplate
                from langchain_core.output_parsers import StrOutputParser

                prompt = PromptTemplate.from_template(self.context)
                chain = prompt | llm | StrOutputParser()

                # Prepare context for chat agents
                invoke_data = {"user_input": user_input}
                if "history" in kwargs:
                    invoke_data["history"] = kwargs["history"]

                response = chain.invoke(invoke_data)

            return response

        except (ValidationError, UserError):
            # Re-raise Odoo exceptions as-is
            raise
        except Exception as e:
            # Log error without exposing sensitive information
            _logger.error(f"Error processing prompt with agent {self.id}: {type(e).__name__}")
            raise UserError(self.env._("Error processing request. Please try again or contact support."))

    @api.model
    def orchestrate(self, user_input: str, chat_history: Optional[List] = None) -> str:
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

            response = agent.execute(
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
            error_msg = "I encountered an error while processing your request. Please try again or contact support."
            _logger.error(f"Error processing prompt for user {self.env.user.id}: {type(e).__name__}")

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
            response = orchestrator.execute(user_input)
            return response.strip().upper()
        except Exception as e:
            _logger.warning(f"Intent classification failed: {e}")
            return "CHAT"

    def _locate_agent(self, intent: str):
        """Locate appropriate agent based on intent."""
        if not intent:
            intent = "CHAT"

        # Define intent to agent type mapping
        intent_mapping = {"INVENTORY_QUERY": "inventory", "SALES_QUERY": "sales", "CHAT": "chat"}

        # Find active agent of the determined type
        agent_type = intent_mapping.get(intent.upper(), "chat")
        agent = self.search(
            [("intent", "=", agent_type), ("active", "=", True)],
            limit=1,
        )

        if not agent:
            # Fallback to chat agent
            agent = self.search(
                [("intent", "=", "chat"), ("active", "=", True)],
                limit=1,
            )

        if not agent:
            raise UserError(
                self.env._("No active agents found to handle the request. Please configure at least one chat agent.")
            )

        return agent

    @api.depends("prompt_ids")
    def _compute_prompt_count(self):
        """Compute total prompts processed by this agent."""
        for agent in self:
            agent.prompt_count = len(agent.prompt_ids)

    def _compute_prompts_today(self):
        """Compute prompts processed today."""
        today = fields.Date.today()
        for agent in self:
            agent.prompts_today = self.env["marin.ai.prompt"].search_count(
                [("agent_id", "=", agent.id), ("create_date", ">=", today)]
            )

    def _compute_prompts_this_week(self):
        """Compute prompts processed this week."""
        week_start = fields.Date.today() - timedelta(days=7)
        for agent in self:
            agent.prompts_this_week = self.env["marin.ai.prompt"].search_count(
                [("agent_id", "=", agent.id), ("create_date", ">=", week_start)]
            )

    def action_view_prompts(self):
        """Action to view prompts for this agent."""
        self.ensure_one()
        return {
            "name": f"Prompts - {self.name}",
            "type": "ir.actions.act_window",
            "res_model": "marin.ai.prompt",
            "view_mode": "list,form",
            "domain": [("agent_id", "=", self.id)],
            "context": {"default_agent_id": self.id},
            "target": "current",
        }

    def action_view_prompts_today(self):
        """Action to view prompts processed today for this agent."""
        self.ensure_one()
        today = fields.Date.today()
        return {
            "name": f"Prompts Today - {self.name}",
            "type": "ir.actions.act_window",
            "res_model": "marin.ai.prompt",
            "view_mode": "list,form",
            "domain": [("agent_id", "=", self.id), ("create_date", ">=", today)],
            "context": {"default_agent_id": self.id},
            "target": "current",
        }

    def action_view_prompts_week(self):
        """Action to view prompts processed this week for this agent."""
        self.ensure_one()
        week_start = fields.Date.today() - timedelta(days=7)
        return {
            "name": f"Prompts This Week - {self.name}",
            "type": "ir.actions.act_window",
            "res_model": "marin.ai.prompt",
            "view_mode": "list,form",
            "domain": [("agent_id", "=", self.id), ("create_date", ">=", week_start)],
            "context": {"default_agent_id": self.id},
            "target": "current",
        }

    def action_view_security_violations(self):
        """Action to view security violations for this agent."""
        self.ensure_one()
        return {
            "name": f"Security Violations - {self.name}",
            "type": "ir.actions.act_window",
            "res_model": "marin.ai.prompt",
            "view_mode": "list,form",
            "domain": [("agent_id", "=", self.id)],
            "context": {"default_agent_id": self.id, "search_default_security_violations": 1},
            "target": "current",
        }
