import json
import os
import re  # Moved import to top level
import time

# from pathlib import Path
from typing import Any, Dict

from langchain_core.exceptions import OutputParserException  # Added for specific exception handling
from langchain_core.output_parsers import PydanticOutputParser  # Updated import
from langchain_core.prompts import ChatPromptTemplate  # Updated import
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

from teshq.utils.logging import log_api_call, log_operation, logger
from teshq.utils.retry import RetryableError, retry_api_call
from teshq.utils.token_tracking import get_token_tracker


class SQLQueryResponse(BaseModel):
    """Simple SQL query response model"""

    query: str
    parameters: Dict[str, Any]


class SQLQueryGenerator:
    """SQL Query Generator — provider-agnostic via LangChain.

    Preferred usage (v2)::

        from teshq.core.llm_factory import build_llm_from_config
        generator = SQLQueryGenerator(llm=build_llm_from_config())

    Legacy usage (Google-only, kept for backward compat)::

        generator = SQLQueryGenerator(api_key="...", model_name="gemini-...")
    """

    DEFAULT_MODEL_NAME = "gemini-2.0-flash-lite"

    def __init__(self, api_key: str = None, model_name: str = None, llm=None):
        self.model_name = model_name or self.DEFAULT_MODEL_NAME

        if llm is not None:
            # v2 path: use the pre-built LLM (Gemini, Azure, or any provider)
            self.llm = llm
            # Try to get a model name for logging; fall back to class default
            self.model_name = (
                getattr(llm, "model_name", None)
                or getattr(llm, "deployment_name", None)
                or getattr(llm, "model", None)
                or self.DEFAULT_MODEL_NAME
            )
        else:
            # Legacy Google-only path — kept for backward compatibility
            if not os.getenv("GOOGLE_API_KEY") and api_key:
                os.environ["GOOGLE_API_KEY"] = api_key
            elif not os.getenv("GOOGLE_API_KEY") and not api_key:
                raise ValueError(
                    "No LLM provided and GOOGLE_API_KEY is not set. "
                    "Pass llm=build_llm_from_config() or set GOOGLE_API_KEY."
                )
            self.llm = ChatGoogleGenerativeAI(model=self.model_name, temperature=0.1)

        # Setup output parser
        self.output_parser = PydanticOutputParser(pydantic_object=SQLQueryResponse)

        # Create prompt template
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self._get_system_prompt()),
                (
                    "human",
                    "Schema:\n{schema}\n\nUser Request: {user_request}\n\nGenerate SQL query with parameters.",
                ),
            ]
        )

    def _get_system_prompt(self) -> str:
        return """You are a precise SQL query generator. Your only job is to output a valid JSON object.

DATABASE DIALECT RULES:
- Write standard ANSI SQL unless the schema specifies a dialect.
- Always use table aliases for multi-table queries.
- For parameterised values use SQLAlchemy named-parameter syntax: :param_name.

OUTPUT FORMAT (strict — no other text):
{{
  "query": "<SQL statement with :named_params>",
  "parameters": {{"param_name": <value>, ...}}
}}

RULES:
1. Output ONLY the JSON object — no markdown, no explanation, no code fences.
2. Every placeholder in the query MUST have a matching key in parameters.
3. If no parameters are needed, output "parameters": {{}}.
4. Infer reasonable, safe parameter values from the user request.
5. Use SELECT by default; only use INSERT/UPDATE/DELETE when explicitly requested.
6. Never DROP, TRUNCATE or ALTER tables.

{format_instructions}"""

    def load_schema(self, schema_file: str) -> str:
        """Load schema from file"""
        with open(schema_file, "r") as f:  # Corrected to use schema_file argument
            return f.read().strip()

    @retry_api_call("llm_api_call")
    def generate_sql(self, user_request: str, schema: str) -> Dict[str, Any]:
        """Generate SQL query from user request and schema with retry logic and logging."""
        start_time = time.time()

        try:
            with log_operation("generate_sql", model=self.model_name, request_length=len(user_request)):
                # Format prompt
                format_instructions = self.output_parser.get_format_instructions()
                messages = self.prompt.format_messages(
                    format_instructions=format_instructions,
                    schema=schema,
                    user_request=user_request,
                )

                # Get response from model with retry on network errors
                try:
                    response = self.llm.invoke(messages)
                except Exception as e:
                    # Convert network/API errors to retryable errors
                    if any(
                        error_type in str(type(e).__name__).lower()
                        for error_type in ["connection", "timeout", "network", "http"]
                    ):
                        logger.warning(f"API call failed with retryable error: {e}")
                        raise RetryableError(f"API call failed: {e}") from e
                    else:
                        raise

                # Parse response
                try:
                    parsed = self.output_parser.parse(response.content)
                    result = {"query": parsed.query, "parameters": parsed.parameters}

                except OutputParserException as e:  # More specific exception
                    logger.warning(
                        "PydanticOutputParser failed, falling back to regex JSON extraction",
                        error=e,
                        response_content_preview=response.content[:200],
                    )

                    # Fallback: extract JSON manually
                    json_match = re.search(r"\{[\s\S]*\}", response.content)  # Improved regex for multiline JSON
                    if json_match:
                        try:
                            result = json.loads(json_match.group())
                        except json.JSONDecodeError as json_e:
                            logger.error(
                                "Could not parse response content as JSON after Pydantic failure",
                                json_error=json_e,
                                response_content=response.content,
                            )
                            raise Exception(
                                f"Could not parse response content as JSON after Pydantic failure. Content: {response.content}. Error: {json_e}"  # noqa: E501
                            )
                    else:
                        logger.error(
                            "Could not find JSON in response content after Pydantic failure",
                            response_content=response.content,
                        )
                        raise Exception(
                            f"Could not parse response or find JSON in content after Pydantic failure. Content: {response.content}"  # noqa: E501
                        )

                # Log successful API call with enhanced token tracking
                execution_time = time.time() - start_time

                # Get token tracker
                tracker = get_token_tracker()
                
                # Extract token usage information from response
                prompt_tokens = 0
                completion_tokens = 0
                total_tokens = 0

                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    # Gemini SDK returns an object; support both attribute-access and dict-access.
                    usage = response.usage_metadata
                    if hasattr(usage, 'prompt_token_count'):
                        # google-generativeai >= 0.5 object style
                        prompt_tokens = getattr(usage, 'prompt_token_count', 0) or 0
                        completion_tokens = getattr(usage, 'candidates_token_count', 0) or 0
                    elif hasattr(usage, 'input_tokens'):
                        # langchain-google-genai dict-like style
                        prompt_tokens = getattr(usage, 'input_tokens', 0) or 0
                        completion_tokens = getattr(usage, 'output_tokens', 0) or 0
                    elif isinstance(usage, dict):
                        prompt_tokens = usage.get('input_tokens', 0) or usage.get('prompt_token_count', 0) or 0
                        completion_tokens = usage.get('output_tokens', 0) or usage.get('candidates_token_count', 0) or 0
                    total_tokens = prompt_tokens + completion_tokens
                elif hasattr(response, 'response_metadata') and response.response_metadata:
                    usage = response.response_metadata.get('usage', {})
                    prompt_tokens = usage.get('prompt_tokens', 0)
                    completion_tokens = usage.get('completion_tokens', 0)
                    total_tokens = usage.get('total_tokens', prompt_tokens + completion_tokens)
                else:
                    # Fallback: rough character-based estimation (1 token ≈ 4 chars)
                    prompt_tokens = len(user_request + schema) // 4
                    completion_tokens = len(str(result)) // 4
                    total_tokens = prompt_tokens + completion_tokens
                    logger.warning(
                        "No usage metadata available, using token estimation",
                        estimated_prompt_tokens=prompt_tokens,
                        estimated_completion_tokens=completion_tokens
                    )

                # Track token usage with comprehensive analytics
                execution_time_ms = execution_time * 1000
                token_usage = tracker.track_usage(
                    model=self.model_name,
                    provider="google",  # Since we're using Google Gemini
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    natural_language_query=user_request,
                    generated_sql=result.get("query"),
                    execution_time_ms=execution_time_ms,
                )

                # Legacy logging for backward compatibility
                log_api_call(
                    provider="google_genai",
                    model=self.model_name,
                    tokens_used=total_tokens,
                    execution_time_seconds=execution_time,
                    request_length=len(user_request),
                    schema_length=len(schema),
                    response_length=len(str(result)),
                )

                logger.success(
                    "SQL query generated successfully with comprehensive token tracking",
                    execution_time_seconds=execution_time,
                    query_id=token_usage.query_id,
                    total_tokens=total_tokens,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cost_estimate=f"${token_usage.cost_estimate:.6f}" if token_usage.cost_estimate else "N/A",
                    query_length=len(result.get("query", "")),
                    has_parameters=bool(result.get("parameters")),
                )

                return result

        except Exception as e:
            execution_time = time.time() - start_time

            logger.error(
                "SQL generation failed",
                error=e,
                execution_time_seconds=execution_time,
                model=self.model_name,
                request_length=len(user_request),
            )
            raise
