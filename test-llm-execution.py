from pathlib import Path

from core.llm import SQLQueryGenerator
from core.query import execute_sql_query
from utils.formater import print_query_table
from utils.keys import get_db_url, get_gemini_credentials


def main():
    """Example usage"""

    # Define schema path
    schema_dir = Path("db_schema")
    schema_file_path = schema_dir / "schema.txt"

    try:
        # Initialize generator
        gemini_api_key, gemini_model_name = get_gemini_credentials()
        generator = SQLQueryGenerator(api_key=gemini_api_key, model_name=gemini_model_name)

        schema = generator.load_schema(str(schema_file_path))

        # Test queries
        test_requests = [
            # Original simple queries
            "What is the minimum and maximum salary for each job title?",
            "What are the different types of relationships recorded for dependents (e.g., Spouse, Child)?",
            "Get average salary by department",  # noqa: E501
            "List employees with salary between 50000 and 80000",  # noqa: E501
            # New, more challenging queries
            "List all employees and their manager's name. If an employee has no manager, display 'No Manager' for the manager's name.",  # noqa: E501
            "Find departments that have more than 3 employees and list the department name and the count of employees.",  # noqa: E501
            "List all departments located in the 'Europe' region, along with their city and country.",  # noqa: E501
            "Find the top 3 highest-paid employees overall. Display their full name, job title, department name, and salary.",  # noqa: E501
            "Identify employees whose salary is either below the min_salary or above the max_salary defined for their job title. List employee name, job title, their salary, and the job's min/max salary.",  # noqa: E501
            "For each department, calculate the average tenure (in years) of its employees. Display department name and average tenure.",  # noqa: E501
            "List employees who have at least one dependent named 'Child' and earn more than the average salary of all employees in the 'IT' department.",  # noqa: E501
            "Which job titles have an average employee salary that is 10% higher than the job's defined `min_salary`?",
            "Find countries that do not have any departments located in them.",
            "For each manager, list their name and the total number of dependents of all employees they directly manage.",  # noqa: E501
            "What is the second highest salary in the entire company? List the salary and the full name(s) of employee(s) earning it.",  # noqa: E501
            "List all employees hired before their current manager.",
        ]

        print("SQL Query Generator Results:")
        print("=" * 50)

        for request in test_requests:
            try:
                result = generator.generate_sql(request, schema)

                print_query_table(
                    request,
                    result.get("query"),
                    result.get("parameters"),
                    execute_sql_query(db_url=get_db_url(), query=result.get("query"), parameters=result.get("parameters")),
                )

            except Exception as e:
                print(f"Error generating SQL for '{request}': {e}")

    except Exception as e:
        print(f"Setup error: {e}")
        print("Make sure GOOGLE_API_KEY is set in your environment or passed correctly,")
        print(f"and that the model name (e.g., '{SQLQueryGenerator.DEFAULT_MODEL_NAME}') is accessible with your key.")


if __name__ == "__main__":
    main()
