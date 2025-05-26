from pathlib import Path

import typer
from sqlalchemy.exc import SQLAlchemyError

from core.llm import SQLQueryGenerator
from core.query import execute_sql_query
from utils.formater import print_query_table
from utils.keys import get_db_url, get_gemini_credentials

app = typer.Typer()


@app.command(
    name="query",
    help="Execute the Natural Language Query On Database and Return the Result",
)
def process_nl_query(natural_language_request: str):
    """
    Processes a natural language query, generates SQL, executes it, and prints the results.
    """

    gemini_api_key, gemini_model = get_gemini_credentials()
    generator = SQLQueryGenerator(api_key=gemini_api_key, model_name=gemini_model)

    schema_dir = Path("db_schema")
    schema_file_path = schema_dir / "schema.txt"

    try:
        typer.echo(f"Loading schema from: {schema_file_path}")
        schema = generator.load_schema(schema_file_path)
    except FileNotFoundError:
        typer.secho(f"Error: Schema file not found at {schema_file_path}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(f"Error loading schema: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.echo(f'Generating SQL for: "{natural_language_request}"')
    try:
        result = generator.generate_sql(natural_language_request, schema)
    except Exception as e:
        typer.secho(f"Error generating SQL: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    sql_query = result.get("query")
    parameters = result.get("parameters")

    if not sql_query:
        typer.secho("Error: SQL generation did not return a query.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.echo(f"Generated SQL: {sql_query}")
    if parameters:
        typer.echo(f"With parameters: {parameters}")

    try:
        db_url_val = get_db_url()
        typer.echo(
            f"Executing query on database: {db_url_val.split('@')[-1] if db_url_val and '@' in db_url_val else 'default DB'}"
        )
        query_execution_result = execute_sql_query(
            db_url=db_url_val,
            query=sql_query,
            parameters=parameters,
        )
    except SQLAlchemyError as e:
        typer.secho(f"Error executing SQL query: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    print_query_table(
        natural_language_request,
        sql_query,
        parameters,
        query_execution_result,
    )
    typer.echo("Query processed successfully.")
