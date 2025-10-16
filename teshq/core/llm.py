import json
import os
import re
import time
from typing import Any, Dict

from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

from teshq.utils.analytics import track_llm_usage
from teshq.utils.logging import logger
from teshq.utils.retry import RetryableError, retry_api_call


class SQLQueryResponse(BaseModel):
    """Pydantic model for a structured SQL query response."""

    query: str
    parameters: Dict[str, Any]


class SQLQueryGenerator:
    """
    A robust SQL Query Generator using Google Generative AI and LangChain.

    This class is responsible for taking a user's natural language request
    and converting it into a structured SQL query. It leverages a large
    language model, handles API retries, and includes detailed logging and
    usage analytics.
    """

    DEFAULT_MODEL_NAME = "gemini-1.5-flash"
    PROVIDER = "google"  # The LLM provider, used for cost tracking.

    def __init__(self, api_key: str = None, model_name: str = None):
        """
        Initializes the SQLQueryGenerator.

        Args:
            api_key: The Google API key. If not provided, it's read from the
                     `GOOGLE_API_KEY` environment variable.
            model_name: The specific Gemini model to use. Defaults to `DEFAULT_MODEL_NAME`.
        """
        self.model_name = model_name if model_name is not None else self.DEFAULT_MODEL_NAME

        # Set up the Google API key from argument or environment variable.
        if not os.getenv("GOOGLE_API_KEY") and api_key:
            os.environ["GOOGLE_API_KEY"] = api_key
        elif not os.getenv("GOOGLE_API_KEY"):
            raise ValueError("GOOGLE_API_KEY must be set as an environment variable or " "passed during initialization.")

        # Initialize the LangChain components.
        self.llm = ChatGoogleGenerativeAI(model=self.model_name, temperature=0.1)
        self.output_parser = PydanticOutputParser(pydantic_object=SQLQueryResponse)
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self._get_system_prompt()),
                (
                    "human",
                    "Schema:\\n{schema}\\n\\nUser Request: {user_request}\\n\\n" "Generate SQL query with parameters.",
                ),
            ]
        )

    def _get_system_prompt(self) -> str:
        """Returns the system prompt, including format instructions for the LLM."""
        return """You are an expert SQL query generator. Your task is to generate SQL queries based on database schemas
        and user requests.

                RULES:
                1. Always use parameterized queries. Use the `:parameter_name` format for placeholders.
                2. Return ONLY a single valid JSON object with 'query' and 'parameters' fields.
                3. Based on the user request, make reasonable and safe assumptions for parameter values.
                4. Ensure the generated SQL syntax is correct and secure.

                {format_instructions}
            """

    def load_schema(self, schema_file: str) -> str:
        """Loads a database schema from a file."""
        with open(schema_file, "r") as f:
            return f.read().strip()

    @retry_api_call("llm_api_call")
    def generate_sql(self, user_request: str, schema: str) -> Dict[str, Any]:
        """
        Generates a SQL query from a user request and a database schema.

        This method includes retry logic for API calls, detailed logging, and
        a fallback mechanism for parsing the LLM's response. It also tracks
        LLM usage and cost via the analytics module.

        Args:
            user_request: The natural language request from the user.
            schema: The database schema as a string.

        Returns:
            A dictionary containing the generated 'query' and its 'parameters'.

        Raises:
            RetryableError: If a transient API error occurs.
            Exception: If a critical error occurs during generation or parsing.
        """
        start_time = time.time()
        logger.info(
            "Starting SQL generation",
            model=self.model_name,
            request_length=len(user_request),
        )

        try:
            # Format the prompt with all necessary information.
            messages = self.prompt.format_messages(
                format_instructions=self.output_parser.get_format_instructions(),
                schema=schema,
                user_request=user_request,
            )

            # Make the API call to the LLM.
            try:
                response = self.llm.invoke(messages)
                # In modern LangChain, token info is in the `usage_metadata` attribute of the AIMessage.
                usage_metadata = response.usage_metadata or {}
            except Exception as e:
                # Isolate and handle network-related errors that are safe to retry.
                error_type = str(type(e).__name__).lower()
                is_retryable = any(err_keyword in error_type for err_keyword in ["connection", "timeout", "network", "http"])
                if is_retryable:
                    logger.warning(f"API call failed with retryable error: {e}")
                    raise RetryableError(f"API call failed: {e}") from e
                else:
                    raise  # Re-raise other, non-retryable API errors.

            # First, try to parse the response with the Pydantic parser for structured output.
            try:
                parsed = self.output_parser.parse(response.content)
                result = {"query": parsed.query, "parameters": parsed.parameters}
            except OutputParserException as e:
                # If Pydantic parsing fails, fall back to a more lenient regex-based JSON extraction.
                logger.warning(
                    "PydanticOutputParser failed, falling back to regex JSON extraction",
                    error=e,
                    response_content_preview=response.content[:200],
                )
                json_match = re.search(r"\{[\s\S]*\}", response.content)
                if json_match:
                    try:
                        result = json.loads(json_match.group())
                    except json.JSONDecodeError as json_e:
                        logger.error(
                            "Could not parse response as JSON after Pydantic failure",
                            json_error=json_e,
                            response_content=response.content,
                        )
                        raise Exception("Could not parse response content as JSON. " f"Error: {json_e}") from json_e
                else:
                    logger.error(
                        "Could not find JSON in response after Pydantic failure",
                        response_content=response.content,
                    )
                    raise Exception("Could not parse response or find JSON in content " "after Pydantic failure.")

            execution_time = time.time() - start_time

            # Correctly extract token usage from the `usage_metadata` object.
            input_tokens = usage_metadata.get("input_tokens", 0)
            output_tokens = usage_metadata.get("output_tokens", 0)
            total_tokens = usage_metadata.get("total_tokens", 0)

            # Track LLM usage and cost via the analytics module.
            track_llm_usage(
                model=self.model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                provider=self.PROVIDER,
            )

            # Log a detailed success message with the correct token counts.
            logger.success(
                "SQL query generated successfully",
                execution_time_seconds=round(execution_time, 2),
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens,
                total_tokens=total_tokens,
                query_length=len(result.get("query", "")),
                has_parameters=bool(result.get("parameters")),
            )

            return result

        except Exception as e:
            # Catch any exception that occurred during the process and log a detailed error.
            execution_time = time.time() - start_time
            logger.error(
                "SQL generation failed",
                error=e,
                execution_time_seconds=round(execution_time, 2),
                model=self.model_name,
                request_length=len(user_request),
            )
            raise  # Re-raise the exception to be handled by the caller.
