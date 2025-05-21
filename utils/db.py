import json
import os

from dotenv import load_dotenv


class DatabaseURLError(Exception):
    """Custom exception for database URL retrieval errors."""


load_dotenv()


def get_db_url():
    """
    Retrieve the database URL from environment variable or config.json.

    Returns:
        str: The database URL.

    Raises:
        DatabaseURLError: If DATABASE_URL is not found in either source.
    """

    db_url = os.getenv("DATABASE_URL")

    # Fallback to config.json if not found in .env
    if not db_url:
        try:
            with open("config.json", "r") as f:
                config_data = json.load(f)
                db_url = config_data.get("DATABASE_URL")
                if db_url:  # Found in config.json
                    print("Using DATABASE_URL from config.json")
                    return db_url
                else:  # Not found in config.json
                    print("DATABASE_URL not found in config.json.")
        except FileNotFoundError:
            print("Error: config.json not found.")
        except json.JSONDecodeError:
            print("Error: config.json is not a valid JSON file.")

    # If db_url is still not set after checking both sources
    if not db_url:
        raise DatabaseURLError(
            "DATABASE_URL not set in either environment variables or config.json. to Config use command teshq config"
        )

    return db_url  # Should not be reached if db_url is not set, but for completeness


if __name__ == "__main__":
    try:
        db_url = get_db_url()
        print(f"Database URL: {db_url}")
    except DatabaseURLError as e:
        print(f"Error: {e}")
