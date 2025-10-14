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

from teshq.utils.logging import logger
from teshq.utils.retry import RetryableError, retry_api_call


class SQLQueryResponse(BaseModel):
    """Simple SQL query response model"""

    query: str
    parameters: Dict[str, Any]


class SQLQueryGenerator:
    """SQL Query Generator using Google GenAI and LangChain"""

    DEFAULT_MODEL_NAME = "gemini-1.5-flash"  # Using a more standard and recent model

    def __init__(self, api_key: str = None, model_name: str = None):
        self.model_name = model_name if model_name is not None else self.DEFAULT_MODEL_NAME

        if not os.getenv("GOOGLE_API_KEY") and api_key:
            os.environ["GOOGLE_API_KEY"] = api_key
        elif not os.getenv("GOOGLE_API_KEY"):
            raise ValueError("GOOGLE_API_KEY must be set")

        self.llm = ChatGoogleGenerativeAI(model=self.model_name, temperature=0.1)
        self.output_parser = PydanticOutputParser(pydantic_object=SQLQueryResponse)
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
        with open(schema_file, "r") as f:
            return f.read().strip()

    @retry_api_call("llm_api_call")
    def generate_sql(self, user_request: str, schema: str) -> Dict[str, Any]:
        """Generate SQL query from user request and schema with retry logic and logging."""
        start_time = time.time()
        logger.info("Starting SQL generation", model=self.model_name, request_length=len(user_request))

        try:
            format_instructions = self.output_parser.get_format_instructions()
            messages = self.prompt.format_messages(
                format_instructions=format_instructions,
                schema=schema,
                user_request=user_request,
            )

            try:
                # The response now includes usage metadata
                response = self.llm.invoke(messages)
                token_usage = response.response_metadata.get("token_usage", {})
            except Exception as e:
                if any(
                    error_type in str(type(e).__name__).lower()
                    for error_type in ["connection", "timeout", "network", "http"]
                ):
                    logger.warning(f"API call failed with retryable error: {e}")
                    raise RetryableError(f"API call failed: {e}") from e
                else:
                    raise

            try:
                parsed = self.output_parser.parse(response.content)
                result = {"query": parsed.query, "parameters": parsed.parameters}

            except OutputParserException as e:
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
                        raise Exception(
                            "Could not parse response content as JSON after Pydantic failure. "
                            f"Content: {response.content}. Error: {json_e}"
                        ) from json_e
                else:
                    logger.error(
                        "Could not find JSON in response after Pydantic failure",
                        response_content=response.content,
                    )
                    raise Exception(
                        "Could not parse response or find JSON in content after Pydantic failure. "
                        f"Content: {response.content}"
                    )

            execution_time = time.time() - start_time

            # Extract actual token usage
            prompt_tokens = token_usage.get("prompt_token_count", 0)
            completion_tokens = token_usage.get("candidates_token_count", 0)
            total_tokens = token_usage.get("total_token_count", 0)

            logger.success(
                "SQL query generated successfully",
                execution_time_seconds=execution_time,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
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
