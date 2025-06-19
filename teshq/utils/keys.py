import json
import os

from dotenv import load_dotenv

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
        return db_url
    else:
        try:
            with open("config.json", "r") as f:
                config_data = json.load(f)
                db_url = config_data.get("DATABASE_URL")
        except (FileNotFoundError, json.JSONDecodeError, Exception):
            pass

    if not db_url:
        raise DatabaseURLError(
            "DATABASE_URL not set in either environment variables or config.json.\n"
            "To configure, use the command: teshq config --db-url YOUR_URL"
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
    """
    api_key: str | None = os.getenv("GEMINI_API_KEY")
    model_name: str | None = os.getenv("GEMINI_MODEL_NAME")

    if not model_name:
        try:
            with open(JSON_CONFIG_FILE, "r") as f:
                config_data = json.load(f)
                model_name = config_data.get("GEMINI_MODEL_NAME", DEFAULT_GEMINI_MODEL)
        except (FileNotFoundError, json.JSONDecodeError, Exception):
            model_name = DEFAULT_GEMINI_MODEL

    return api_key, model_name


if __name__ == "__main__":
    try:
        db_url = get_db_url()
        gemini_api_key, gemini_model_name = get_gemini_credentials()
        print(f"Database URL: {db_url}")
        print(f"Gemini API Key: {gemini_api_key}")
        print(f"Gemini Model Name: {gemini_model_name}")
    except DatabaseURLError as e:
        print(f"Error: {e}")
