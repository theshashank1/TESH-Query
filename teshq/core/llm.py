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

                # Log successful API call
                execution_time = time.time() - start_time

                # Estimate token usage (rough approximation)
                estimated_tokens = len(user_request + schema + str(result)) // 4

                log_api_call(
                    provider="google_genai",
                    model=self.model_name,
                    tokens_used=estimated_tokens,
                    execution_time_seconds=execution_time,
                    request_length=len(user_request),
                    schema_length=len(schema),
                    response_length=len(str(result)),
                )

                logger.success(
                    "SQL query generated successfully",
                    execution_time_seconds=execution_time,
                    estimated_tokens=estimated_tokens,
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
