import json
import os
import re  # Moved import to top level
from pathlib import Path
from typing import Any, Dict

from langchain_core.exceptions import OutputParserException  # Added for specific exception handling
from langchain_core.output_parsers import PydanticOutputParser  # Updated import
from langchain_core.prompts import ChatPromptTemplate  # Updated import
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel


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

    def generate_sql(self, user_request: str, schema: str) -> Dict[str, Any]:
        """Generate SQL query from user request and schema"""

        # Format prompt
        format_instructions = self.output_parser.get_format_instructions()
        messages = self.prompt.format_messages(
            format_instructions=format_instructions,
            schema=schema,
            user_request=user_request,
        )

        # Get response from model
        response = self.llm.invoke(messages)

        # Parse response
        try:
            parsed = self.output_parser.parse(response.content)
            return {"query": parsed.query, "parameters": parsed.parameters}
        except OutputParserException as e:  # More specific exception
            print(f"Warning: PydanticOutputParser failed ({e}). Falling back to regex JSON extraction.")
            # Fallback: extract JSON manually
            json_match = re.search(r"\{[\s\S]*\}", response.content)  # Improved regex for multiline JSON
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError as json_e:
                    raise Exception(
                        f"Could not parse response content as JSON after Pydantic failure. Content: {response.content}. Error: {json_e}"  # noqa: E501
                    )
            else:
                raise Exception(
                    f"Could not parse response or find JSON in content after Pydantic failure. Content: {response.content}"
                )


def main():
    """Example usage"""

    # Define schema path
    schema_dir = Path("db_schema")
    schema_file_path = schema_dir / "schema.txt"

    # Create sample schema.txt if it doesn't exist
    if not schema_file_path.exists():
        schema_dir.mkdir(parents=True, exist_ok=True)  # Create directory if it doesn't exist
        sample_schema = """Table: employees
Columns:
- id (INTEGER)
- name (TEXT)
- department (TEXT)
- salary (INTEGER)
- hire_date (DATE)

Table: departments
Columns:
- id (INTEGER)
- name (TEXT)
- budget (INTEGER)"""

        with open(schema_file_path, "w") as f:
            f.write(sample_schema)
        print(f"Created sample schema at {schema_file_path}")

    try:
        # Initialize generator
        # Note: The API key "AIzaSy..." is a placeholder.
        # Ensure a valid GOOGLE_API_KEY is set in your environment or passed here.
        # You can also specify a model here, e.g., model_name="gemini-1.5-flash-latest"
        generator = SQLQueryGenerator(api_key="AIzaSyC1l44qiKYj******9FXJgHjdZHQhtSTtI")

        # Load schema
        schema = generator.load_schema(str(schema_file_path))  # Pass the correct path as string

        # Test queries
        test_requests = [
            "Get all employees in the Engineering department with salary above 60000",
            "Find employees hired after 2020",
            "Get average salary by department",
            "List employees with salary between 50000 and 80000",
        ]

        print("SQL Query Generator Results:")
        print("=" * 50)

        for request in test_requests:
            print(f"\nRequest: {request}")
            print("-" * 40)

            try:
                result = generator.generate_sql(request, schema)
                print(json.dumps(result, indent=2))
            except Exception as e:
                print(f"Error generating SQL for '{request}': {e}")

    except Exception as e:
        print(f"Setup error: {e}")
        print("Make sure GOOGLE_API_KEY is set in your environment or passed correctly,")
        # Use the class attribute for the default model name in the error message
        print(f"and that the model name (e.g., '{SQLQueryGenerator.DEFAULT_MODEL_NAME}') is accessible with your key.")


if __name__ == "__main__":
    main()
