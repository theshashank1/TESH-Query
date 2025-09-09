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
    """SQL Query Generator using Google GenAI and LangChain"""

    DEFAULT_MODEL_NAME = "gemini-2.0-flash-lite"  # Class attribute for default model

    def __init__(self, api_key: str = None, model_name: str = None):
        # Use class default if no model_name is provided
        self.model_name = model_name if model_name is not None else self.DEFAULT_MODEL_NAME

        # Set API key
        if not os.getenv("GOOGLE_API_KEY") and api_key:
            os.environ["GOOGLE_API_KEY"] = api_key
        elif not os.getenv("GOOGLE_API_KEY"):
            raise ValueError("GOOGLE_API_KEY must be set")

        # Initialize model
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
        return """You are a SQL query generator. Generate SQL queries based on database schemas and user requests.

                RULES:
                1. Use parameterized queries with :parameter_name format
                2. Return only JSON with 'query' and 'parameters' fields
                3. Make reasonable parameter values based on the user request
                4. Use proper SQL syntax

                {format_instructions}
            """

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
                    # For Google Gemini models
                    usage = response.usage_metadata
                    prompt_tokens = usage.get('input_tokens', 0)
                    completion_tokens = usage.get('output_tokens', 0)
                    total_tokens = prompt_tokens + completion_tokens
                elif hasattr(response, 'response_metadata') and response.response_metadata:
                    # Alternative location for usage data
                    usage = response.response_metadata.get('usage', {})
                    prompt_tokens = usage.get('prompt_tokens', 0)
                    completion_tokens = usage.get('completion_tokens', 0)
                    total_tokens = usage.get('total_tokens', prompt_tokens + completion_tokens)
                else:
                    # Fallback: estimate tokens based on content length
                    # Rough approximation: 1 token ≈ 4 characters
                    prompt_text = user_request + schema
                    prompt_tokens = len(prompt_text) // 4
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
