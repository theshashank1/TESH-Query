import json
import os

from dotenv import load_dotenv
from rich.console import Console

# Initialize Rich console
console = Console()

# Constants
JSON_CONFIG_FILE = "config.json"
DEFAULT_GEMINI_MODEL = "gemini-pro"


# --- Custom Exceptions ---
class DatabaseURLError(Exception):
    """Custom exception raised when the database URL cannot be retrieved."""

    pass


class GeminiCredentialsError(Exception):
    """Custom exception raised when Gemini credentials cannot be retrieved."""

    pass


# Load environment variables from .env file
load_dotenv()


def get_db_url():
    """
    Retrieve the database URL from environment variable or config.json.

    Returns:
        str: The database URL.

    Raises:
        DatabaseURLError: If DATABASE_URL is not found in either source.
    """
    db_url: str | None = os.getenv("DATABASE_URL")

    if db_url:
        console.log("[bold green]Using DATABASE_URL from environment variables.[/]")  # type: ignore
    else:
        # Fallback to config.json if not found in .env
        console.log("[yellow]DATABASE_URL not found in environment variables. Checking config.json...[/]")  # noqa: E501
        try:
            with open("config.json", "r") as f:
                config_data = json.load(f)
                db_url = config_data.get("DATABASE_URL")
                if db_url:  # type: ignore
                    console.log("[bold green]Using DATABASE_URL from config.json.[/]")
                else:
                    console.log("[bold yellow]DATABASE_URL not found in config.json.[/]")
        except FileNotFoundError:
            console.log("[bold red]Error:[/] config.json not found.")
        except json.JSONDecodeError:  # type: ignore
            console.log("[bold red]Error:[/] config.json is not a valid JSON file.")
        except Exception as e:
            console.log(f"[bold red]Unexpected error while reading config.json:[/] {e}")

    if not db_url:
        raise DatabaseURLError(
            "DATABASE_URL not set in either environment variables or config.json.\n"
            "To configure, use the command: [bold cyan]teshq config --db-url YOUR_URL[/]"
        )

    return db_url


def get_gemini_credentials() -> tuple[str | None, str]:
    """
    Retrieve the Gemini API key and model name.
    Prioritizes environment variables, then falls back to config.json for the model name.
    The API key is expected to be primarily in the .env file for security.

    Returns:
        tuple[str | None, str]: A tuple containing (api_key, model_name).
                                 api_key will be None if not found.
                                 model_name will default if not found.

    Raises:
        GeminiCredentialsError: If the API key is explicitly required but not found.
    """
    api_key: str | None = os.getenv("GEMINI_API_KEY")
    model_name: str | None = os.getenv("GEMINI_MODEL_NAME")

    if model_name:
        console.log(f"[bold green]Using GEMINI_MODEL_NAME[/] '{model_name}' from environment variables.")  # type: ignore
    else:
        console.log("[yellow]GEMINI_MODEL_NAME not found in environment variables. Checking config.json...[/]")
        try:
            with open(JSON_CONFIG_FILE, "r") as f:
                config_data = json.load(f)
                model_name = config_data.get("GEMINI_MODEL_NAME")
                if model_name:  # type: ignore
                    console.log(f"[bold green]Using GEMINI_MODEL_NAME[/] '{model_name}' from {JSON_CONFIG_FILE}.")
                else:
                    console.log(
                        f"[bold yellow]GEMINI_MODEL_NAME not found in {JSON_CONFIG_FILE}. Using default: '{DEFAULT_GEMINI_MODEL}'.[/]"  # noqa: E501
                    )
                    model_name = DEFAULT_GEMINI_MODEL
        except FileNotFoundError:
            console.log(
                f"[bold yellow]Warning:[/] {JSON_CONFIG_FILE} not found. Using default model: '{DEFAULT_GEMINI_MODEL}'."
            )
            model_name = DEFAULT_GEMINI_MODEL
        except json.JSONDecodeError:
            console.log(  # type: ignore
                f"[bold yellow]Warning:[/] {JSON_CONFIG_FILE} is not a valid JSON file. Using default model: '{DEFAULT_GEMINI_MODEL}'."  # noqa: E501
            )
            model_name = DEFAULT_GEMINI_MODEL
        except Exception as e:
            console.log(
                f"[bold yellow]Warning:[/] An unexpected error occurred while reading {JSON_CONFIG_FILE}: {e}. Using default model."  # noqa: E501
            )
            model_name = DEFAULT_GEMINI_MODEL

    if not api_key:
        console.log(
            "[bold yellow]Warning:[/] GEMINI_API_KEY not found in environment variables. Gemini functionality requiring an API key may be limited or fail. "  # noqa: E501
            "Configure it using 'teshq config --gemini-api-key YOUR_KEY' or 'teshq config --config-gemini'."
        )

    return api_key, model_name


if __name__ == "__main__":
    try:
        db_url = get_db_url()
        gemini_api_key, gemini_model_name = get_gemini_credentials()
        console.log(f"[bold blue]Database URL:[/] {db_url}")  # type: ignore
        console.log(f"[bold blue]Gemini API Key:[/] {gemini_api_key}")  # type: ignore
        console.log(f"[bold blue]Gemini Model Name:[/] {gemini_model_name}")  # type: ignore
    except DatabaseURLError as e:
        console.log(f"[bold red]Error:[/] {e}")
